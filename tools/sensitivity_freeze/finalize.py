"""Generate final NOT ACCEPTED candidate after implementation commit; no generation."""
from contextlib import closing
import json
from pathlib import Path
from rest_api_checker import sensitivity_candidate as sc
from rest_api_checker.experiment.encoding import digest
from rest_api_checker.persistence.database import connect,read_settings
from rest_api_checker.persistence.repository import Repository


def main():
    root=Path(__file__).resolve().parents[2];research=root.parent/'bachelor_rest_api_checker'
    with closing(connect(read_settings(Path.home()/'.config/rest-api-checker/application-credentials.env'),'rest_api_checker')) as cn:
        candidate=sc.build(Repository(cn),root,research,root/sc.DIRECTORY)
        cn.rollback()
    print(json.dumps(dict(path=str(root/sc.DIRECTORY/'candidate.json'),
        sha256=digest((root/sc.DIRECTORY/'candidate.json').read_bytes()),status=candidate['status']),indent=2))

if __name__=='__main__':main()
