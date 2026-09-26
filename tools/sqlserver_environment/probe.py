"""Disposable SQL Server compatibility probe. Never reads study artifacts.

Run each phase explicitly; failures preserve evidence and stop the phase.
No cleanup, application tables, migrations, Oracle imports, or provider calls.
"""

import argparse
from contextlib import closing
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import platform
import re
import struct
import sys

import pyodbc


DATABASE = "rac_env_probe_20260926"
RESTORED = "rac_env_probe_restore_20260926"
BACKUP = "/var/opt/mssql/backup/rac_env_probe_20260926.bak"
RESTORE_BACKUP = "/var/opt/mssql/backup/host_copy_for_restore.bak"
PAYLOADS = [b"", b'{"broken":', b"\xff\xfe\x00\x80", bytes(range(256)) * 4096 + b"large-payload-end"]
TEXTS = ["Grüße 中文 😀 e\u0301 é\r\n  ", "", "строка\t終", "large Unicode 🧪 " * 1024]
DECIMALS = [Decimal(s) for s in ("0.200", "0.900", "0.000", "1.000")]
TIMES = ["2026-09-26T13:14:15.1234567+05:45", "2026-09-26T01:02:03.0000000-03:30",
         "2026-09-26T22:23:24.9999999+00:00", "2026-09-26T12:00:00.0000001+02:00"]
FLAGS = [False, None, True, False]
VERDICTS = ["PASS", "FAIL", "NOT_APPLICABLE", "PASS"]
INSERT = """INSERT INTO dbo.probe_value
    (id, parent_id, scope_id, content, expected_sha256, text_value, config_value, captured_at, flag, verdict)
    VALUES (?, ?, ?, ?, ?, ?, ?, CONVERT(datetimeoffset(7), ?, 127), ?, ?)"""


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def decode_datetimeoffset(raw):
    """Decode the SQL_SS_TIMESTAMPOFFSET struct without losing 100 ns precision."""
    year, month, day, hour, minute, second, nanos, tz_hour, tz_minute = struct.unpack("<6hI2h", raw)
    require(nanos % 100 == 0, "Timestamp is not representable at SQL's 100 ns precision")
    offset = tz_hour * 60 + tz_minute
    sign = "+" if offset >= 0 else "-"
    return (f"{year:04}-{month:02}-{day:02}T{hour:02}:{minute:02}:{second:02}."
            f"{nanos // 100:07}{sign}{abs(offset) // 60:02}:{abs(offset) % 60:02}")


def read_settings(path):
    require(path.stat().st_mode & 0o077 == 0, "Credential file must be private (0600)")
    settings = dict(line.split("=", 1) for line in path.read_text().splitlines() if line)
    require(set(settings) == {"RAC_SQL_PASSWORD", "RAC_SQL_PORT"}, "Unexpected credential fields")
    require(re.fullmatch(r"[0-9]+", settings["RAC_SQL_PORT"]) is not None, "Invalid port")
    require(1024 <= int(settings["RAC_SQL_PORT"]) <= 65535, "Invalid port range")
    return settings


def connect(settings, database="master", autocommit=False):
    require(database in {"master", DATABASE, RESTORED}, "Database outside probe scope")
    password = settings["RAC_SQL_PASSWORD"].replace("}", "}}")
    connection = pyodbc.connect(
        "DRIVER={ODBC Driver 18 for SQL Server};SERVER=tcp:127.0.0.1,"
        + settings["RAC_SQL_PORT"] + ";DATABASE=" + database
        + ";UID=sa;PWD={" + password + "};Encrypt=yes;TrustServerCertificate=yes;"
        "APP=RestApiCheckerDisposableEnvironmentProbe;Connection Timeout=10;",
        autocommit=autocommit, timeout=10,
    )
    connection.timeout = 60
    connection.add_output_converter(-155, decode_datetimeoffset)
    return connection


def params(index):
    return (index + 1, 1, 101, pyodbc.Binary(PAYLOADS[index]), sha256(PAYLOADS[index]).hexdigest(),
            TEXTS[index], DECIMALS[index], TIMES[index], FLAGS[index], VERDICTS[index])


def snapshot(settings, database):
    with closing(connect(settings, database)) as cn:
        parents = [list(row) for row in cn.execute("SELECT id,scope_id FROM dbo.probe_parent ORDER BY id")]
        require(parents == [[1, 101], [2, 202], [3, 303]], "Parent/commit/rollback mismatch")
        rows = cn.execute("""SELECT v.id,v.parent_id,v.scope_id,v.content,v.expected_sha256,
            v.text_value,v.config_value,v.captured_at,v.flag,v.verdict,
            DATALENGTH(v.content),DATALENGTH(v.text_value),
            LOWER(CONVERT(varchar(64),HASHBYTES('SHA2_256',v.content),2))
            FROM dbo.probe_value v ORDER BY v.id""").fetchall()
        require(len(rows) == 4, "Unexpected fixture row count")
        evidence = []
        for i, row in enumerate(rows):
            expected = params(i)
            require(bytes(row.content) == PAYLOADS[i], f"Byte mismatch {i}")
            digest = sha256(bytes(row.content)).hexdigest()
            require(digest == expected[4] == row.expected_sha256 == row[12], f"Hash mismatch {i}")
            require((row.id, row.parent_id, row.scope_id) == expected[:3], "Relationship mismatch")
            require(row.text_value == TEXTS[i], f"Unicode mismatch {i}")
            require(isinstance(row.config_value, Decimal) and row.config_value.as_tuple() == DECIMALS[i].as_tuple(), "Decimal value/scale mismatch")
            require(row[7] == TIMES[i], f"Timestamp/offset/100ns mismatch: {row[7]!r}")
            require(row.flag is FLAGS[i], "BIT false/NULL/true mismatch")
            require(row.verdict == VERDICTS[i], "Verdict mismatch")
            require(row[10] == len(PAYLOADS[i]) and row[11] == len(TEXTS[i].encode("utf-16-le")), "Stored length mismatch")
            evidence.append({"id": row.id, "parent_id": row.parent_id, "scope_id": row.scope_id,
                "bytes": row[10], "sha256_expected": expected[4], "sha256_retrieved": digest,
                "sha256_sql": row[12], "exact_bytes_equal": True,
                "text_utf8_sha256": sha256(row.text_value.encode("utf-8")).hexdigest(),
                "text_utf16_bytes": row[11], "exact_unicode_equal": True,
                "decimal": str(row.config_value), "timestamp_with_offset": row[7],
                "flag": row.flag, "verdict": row.verdict})
        require(cn.execute("""SELECT COUNT(*) FROM dbo.probe_value v JOIN dbo.probe_parent p
            ON p.id=v.parent_id AND p.scope_id=v.scope_id""").fetchval() == 4, "Join mismatch")
        constraints = [list(r) for r in cn.execute("""SELECT name,is_disabled,is_not_trusted
            FROM sys.foreign_keys UNION ALL SELECT name,is_disabled,is_not_trusted
            FROM sys.check_constraints ORDER BY name""")]
        require(len(constraints) == 2 and all(r[1:] == [False, False] for r in constraints), "Constraint state mismatch")
        return {"parents": parents, "rows": evidence, "joined_rows": 4, "constraints": constraints}


def initialize(settings, evidence):
    with closing(connect(settings, autocommit=True)) as cn:
        require(cn.execute("SELECT DB_ID(?)", DATABASE).fetchval() is None, "Refusing existing database")
        cn.execute(f"CREATE DATABASE [{DATABASE}]")
    with closing(connect(settings, DATABASE)) as cn:
        cn.execute("""CREATE TABLE dbo.probe_parent (
            id int NOT NULL PRIMARY KEY, scope_id int NOT NULL,
            CONSTRAINT uq_probe_parent UNIQUE (id,scope_id));
            CREATE TABLE dbo.probe_value (
            id int NOT NULL PRIMARY KEY, parent_id int NOT NULL, scope_id int NOT NULL,
            content varbinary(max) NOT NULL, expected_sha256 char(64) NOT NULL,
            text_value nvarchar(max) NOT NULL, config_value decimal(5,3) NOT NULL,
            captured_at datetimeoffset(7) NOT NULL, flag bit NULL,
            verdict varchar(64) COLLATE Latin1_General_100_BIN2 NOT NULL,
            CONSTRAINT fk_probe_pair FOREIGN KEY (parent_id,scope_id)
                REFERENCES dbo.probe_parent(id,scope_id),
            CONSTRAINT ck_probe_verdict CHECK (
                (verdict IN ('PASS','FAIL') AND DATALENGTH(verdict)=4)
                OR (verdict='NOT_APPLICABLE' AND DATALENGTH(verdict)=14)))""")
        cn.execute("INSERT INTO dbo.probe_parent VALUES (1,101),(2,202)")
        for i in range(4):
            cn.execute(INSERT, params(i))
        cn.commit()
        evidence["fixture_insert"] = "PASS"
        rejected = []

        def reject(name, statement, values, numbers):
            try:
                cn.execute(statement, values)
            except pyodbc.IntegrityError as exc:
                cn.rollback()
                message = str(exc)
                require(exc.args[0] == "23000" and any(f"({n})" in message for n in numbers), "Unexpected constraint diagnostic")
                rejected.append({"check": name, "result": "PASS", "sqlstate": exc.args[0], "diagnostic": message})
            else:
                cn.rollback()
                raise RuntimeError(f"Invalid fixture was accepted: {name}")

        reject("composite_fk_wrong_pair", "INSERT INTO dbo.probe_value SELECT 90,2,101,content,expected_sha256,text_value,config_value,captured_at,flag,verdict FROM dbo.probe_value WHERE id=1", (), [547])
        reject("unique_key", "INSERT INTO dbo.probe_parent VALUES (?,?)", (1,101), [2601,2627])
        reject("not_null_content", "UPDATE dbo.probe_value SET content=? WHERE id=1", (None,), [515])
        for token in ["pass", "Pass", "fail", "not_applicable", "PASS ", " PASS", "PASS\t", "NOT_APPLICABLE ", "", "UNKNOWN", None]:
            reject(f"verdict_{token!r}", "UPDATE dbo.probe_value SET verdict=? WHERE id=1", (token,), [515] if token is None else [547])
        evidence["constraints"] = rejected
        cn.execute("INSERT INTO dbo.probe_parent VALUES (3,303)")
        cn.commit()
        with closing(connect(settings, DATABASE)) as observer:
            require(observer.execute("SELECT COUNT(*) FROM dbo.probe_parent WHERE id=3").fetchval() == 1, "Commit invisible to new connection")
        cn.execute("INSERT INTO dbo.probe_parent VALUES (4,404)")
        cn.execute("UPDATE dbo.probe_value SET text_value=N'rollback sentinel' WHERE id=1")
        cn.rollback()
        evidence["commit_and_rollback"] = "PASS (new connection sees committed row; rolled-back insert/update absent)"
    evidence["snapshot"] = snapshot(settings, DATABASE)


def drain(cursor):
    while cursor.nextset():
        pass


def unique(settings, evidence):
    """Exercise an independent UNIQUE key, not only primary-key uniqueness."""
    with closing(connect(settings, DATABASE)) as cn:
        cn.execute("CREATE TABLE #probe_unique (id int PRIMARY KEY, token varchar(16) NOT NULL UNIQUE)")
        cn.execute("INSERT INTO #probe_unique VALUES (1,'same')")
        cn.commit()
        try:
            cn.execute("INSERT INTO #probe_unique VALUES (2,'same')")
        except pyodbc.IntegrityError as exc:
            cn.rollback()
            require(exc.args[0] == "23000" and "(2627)" in str(exc) and "UNIQUE KEY" in str(exc),
                    "Unexpected unique-key diagnostic")
            evidence["independent_unique_key"] = {"result": "PASS", "diagnostic": str(exc)}
        else:
            cn.rollback()
            raise RuntimeError("Duplicate non-primary unique value accepted")


def backup(settings, evidence):
    evidence["snapshot"] = snapshot(settings, DATABASE)
    with closing(connect(settings, autocommit=True)) as cn:
        require(cn.execute("SELECT file_exists FROM sys.dm_os_file_exists(?)", BACKUP).fetchval() == 0,
                "Refusing an existing backup file")
        drain(cn.execute(f"BACKUP DATABASE [{DATABASE}] TO DISK=? WITH COPY_ONLY, NOINIT, CHECKSUM", BACKUP))
        drain(cn.execute("RESTORE VERIFYONLY FROM DISK=? WITH CHECKSUM", BACKUP))
        evidence["backup"] = {"path": BACKUP, "copy_only": True, "checksum": True, "verifyonly": "PASS"}


def restore(settings, evidence):
    original = snapshot(settings, DATABASE)
    with closing(connect(settings, autocommit=True)) as cn:
        require(cn.execute("SELECT DB_ID(?)", RESTORED).fetchval() is None, "Refusing existing restore database")
        files = cn.execute("RESTORE FILELISTONLY FROM DISK=?", RESTORE_BACKUP).fetchall()
        require(len(files) == 2 and {r.Type for r in files} == {"D", "L"}, "Unexpected backup file layout")
        logical = {r.Type: r.LogicalName for r in files}
        require(logical == {"D": DATABASE, "L": DATABASE + "_log"}, "Unexpected backup identity")
        drain(cn.execute(f"""RESTORE DATABASE [{RESTORED}] FROM DISK=? WITH
            MOVE N'{DATABASE}' TO N'/var/opt/mssql/data/{RESTORED}.mdf',
            MOVE N'{DATABASE}_log' TO N'/var/opt/mssql/data/{RESTORED}_log.ldf',
            CHECKSUM, RECOVERY""", RESTORE_BACKUP))
        evidence["backup_file_list"] = [{"logical_name": r.LogicalName, "type": r.Type} for r in files]
    restored = snapshot(settings, RESTORED)
    require(original == restored == snapshot(settings, DATABASE), "Restore/original snapshot mismatch")
    evidence["restored_snapshot"] = restored
    evidence["original_unchanged_and_restored_equal"] = True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["initialize", "verify", "unique", "backup", "restore"])
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    require(not args.evidence.exists(), "Refusing to overwrite evidence")
    settings = read_settings(args.env_file)
    evidence = {"phase": args.phase, "started_at": datetime.now(timezone.utc).isoformat(),
        "python": sys.version, "host_architecture": platform.machine(), "pyodbc": pyodbc.version,
        "endpoint": "127.0.0.1:" + settings["RAC_SQL_PORT"], "database": DATABASE,
        "tls": {"Encrypt": "yes", "TrustServerCertificate": "yes", "scope": "this disposable localhost connection only"},
        "timestamp_transport": "Explicit ISO-8601 input to DATETIMEOFFSET(7); native SQL_SS_TIMESTAMPOFFSET output converter preserves all 7 fractional digits and original offset. No UTC normalization or Python datetime microsecond truncation."}
    try:
        with closing(connect(settings, autocommit=True)) as cn:
            evidence["connection"] = "PASS"
            evidence["driver"] = {"name": cn.getinfo(pyodbc.SQL_DRIVER_NAME), "version": cn.getinfo(pyodbc.SQL_DRIVER_VER), "odbc_version": cn.getinfo(pyodbc.SQL_ODBC_VER)}
            row = cn.execute("""SELECT @@VERSION, CAST(SERVERPROPERTY('ProductVersion') AS varchar(128)),
                CAST(SERVERPROPERTY('Edition') AS varchar(128)), CAST(SERVERPROPERTY('ProductUpdateLevel') AS varchar(128))""").fetchone()
            evidence["engine"] = dict(zip(["version_string", "product_version", "edition", "cu"], row))
            require(row[1].startswith("16.") and "Developer" in row[2] and row[3] == "CU27", "Unexpected engine")
            evidence["connection_observation"] = list(cn.execute("SELECT net_transport,encrypt_option,auth_scheme FROM sys.dm_exec_connections WHERE session_id=@@SPID").fetchone())
        if args.phase == "verify":
            evidence["snapshot"] = snapshot(settings, DATABASE)
        else:
            {"initialize": initialize, "unique": unique, "backup": backup, "restore": restore}[args.phase](settings, evidence)
        evidence["result"] = "PASS"
    except Exception as exc:
        evidence["result"] = "FAIL"
        evidence["error"] = str(exc).replace(settings["RAC_SQL_PASSWORD"], "[REDACTED]")
    evidence["finished_at"] = datetime.now(timezone.utc).isoformat()
    with args.evidence.open("x", encoding="utf-8") as stream:
        json.dump(evidence, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"phase": args.phase, "result": evidence["result"], "evidence": str(args.evidence)}))
    return 0 if evidence["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
