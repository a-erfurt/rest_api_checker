"""Sequential persisted-schedule execution with injectable, verified dispatch context."""
from dataclasses import dataclass
import json
import signal
import threading

from ..persistence.database import require, utc_now
from ..persistence.inspection import bindings, rows, status
from .orchestration import execute_attempt, Paused, prepare
from .request import ContextProof


@dataclass
class StopRequest:
    requested: bool = False


def run(repo, experiment_id, *, client, spool_directory, verify_runtime,
        review_failure, notify=lambda event: None, stop=None, prepare_request=prepare):
    """Retries remain attempts of one run; reserved ambiguous slots never dispatch.

    SIGINT requests a cooperative stop after the active attempt has been durably
    reconciled. A provider timeout bounds that wait. No SQL work occurs in the
    signal handler. Tests can also inject StopRequest or KeyboardInterrupt.
    """
    stop = stop or StopRequest()
    old_handler = None
    if threading.current_thread() is threading.main_thread():
        old_handler = signal.getsignal(signal.SIGINT)
        def interrupt(signum, frame):
            stop.requested = True
            notify({'event':'interrupt_requested', 'message':'Stopping after current attempt persistence; no new work will be scheduled.'})
        signal.signal(signal.SIGINT, interrupt)
    blocked = None
    try:
        with repo.dispatch_owner():
            state = status(repo,experiment_id)
            setup = json.loads(repo.file(state['experiment']['setup_file_id']))
            require(setup.get('bindings')==bindings(repo,state['experiment']['dataset_id'],setup['schedule']),
                    'Missing frozen bindings or configuration/reference drift')
            repo.cn.commit()
            notify(dict(event='start',state=state))
            for scheduled in state['runs']:
                if stop.requested:
                    break
                run_id = scheduled['id']
                while repo._row('experiment_runs',run_id)['result'] is None and not stop.requested:
                    attempts = rows(repo,'run_attempts',run_id=run_id)
                    if not attempts:
                        attempt = 1
                    elif (len(attempts)==1 and attempts[0]['attempt']==1 and attempts[0]['result']=='technical_failure'
                          and repo._diagnostic_root(attempts[0]['diagnostics_file_id']).get('retry_eligible') is True):
                        attempt = 2
                    else:
                        raise Paused('NEEDS RECONCILIATION: reserved or ambiguous dispatch; provider was not called again')
                    current = dict(run_id=run_id,model=repo._row('models',scheduled['model_id'])['name'],
                        prompt=repo._row('prompts',scheduled['prompt_id'])['name'],
                        case=repo._row('dataset_cases',scheduled['dataset_case_id'])['case_code'],
                        repetition=scheduled['repetition'],attempt=attempt)
                    repo.cn.commit()
                    if attempt==2:
                        notify(dict(event='retry',current=current,message='Technical failure — retrying identical request (attempt 2/2)'))
                    notify(dict(event='current',current=current))
                    execute_attempt(repo,run_id,attempt=attempt,client=client,spool_directory=spool_directory,
                        context_proof=ContextProof(**setup['context_proofs'][str(scheduled['run_order'])]),
                        verify_runtime=verify_runtime,review_failure=review_failure,
                        prepare_request=prepare_request)
                    state = status(repo,experiment_id)
                    repo.cn.commit()
                    notify(dict(event='progress',state=state))
            state = status(repo,experiment_id)
            repo.cn.commit()
            if state['pending']==0 and state['experiment']['finished_at'] is None:
                repo.complete_experiment(experiment_id,finished_at=utc_now())
    except KeyboardInterrupt:
        stop.requested = True
        blocked = 'Interrupted before safe completion; inspect reserved attempts and reconcile durable spools before resume.'
    except (Paused, ValueError, OSError) as exc:
        blocked = str(exc)
    finally:
        if old_handler is not None:
            signal.signal(signal.SIGINT,old_handler)
    state = status(repo,experiment_id)
    repo.cn.commit()
    code = 130 if stop.requested else 3 if blocked or state['pending'] else 0
    result = dict(state=state,exit_code=code,status='COMPLETED' if code==0 else 'INCOMPLETE' if code==130 else 'BLOCKED',
                  message=blocked,inspect=f'inspect run <run-id>; experiment show {experiment_id}',
                  resume=f'experiment resume {experiment_id}')
    notify(dict(event='finish',**result))
    return result
