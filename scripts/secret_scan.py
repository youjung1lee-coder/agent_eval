"""Scan Git index (or explicitly selected source files) without printing secret values."""
import argparse
from pathlib import Path
import re
import subprocess
import sys

PATTERNS = [
    ("private key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("GitHub token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b")),
    ("AWS access key", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("provider token", re.compile(r"\bsk-[A-Za-z0-9_-]{25,}\b")),
    ("assigned credential", re.compile(r'''(?m)^[ \t]*(?:[A-Z_]*(?:API_KEY|PASSWORD|SECRET|TOKEN|CREDENTIAL)[A-Z_]*)[ \t]*=[ \t]*["']?([^\s"'#]{12,})''')),
]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--source",action="store_true",help="Scan allow-listed source before staging")
    args=parser.parse_args()
    root=Path.cwd().resolve()
    if args.source:
        files=[f for directory in ("evaluation_platform","sample_agents","tests","scripts","docs","ui") for f in Path(directory).rglob("*") if f.is_file() and f.suffix in (".py",".js",".cjs",".json",".md",".html",".css")]
        files += [Path(p) for p in ("README.md","requirements.txt","requirements-phoenix.txt",".env.example",".gitignore","package.json","pytest.ini") if Path(p).exists()]
        contents=[(str(f), f.read_text(encoding="utf-8-sig")) for f in files]
    else:
        git=["git","-c","safe.directory="+root.as_posix()]
        names=subprocess.check_output(git+["diff","--cached","--name-only","-z"],text=True).split("\0")
        contents=[]
        for name in filter(None,names):
            if name==".env" or (name.startswith(".env.") and name!=".env.example") or name.split("/")[0] in ("data",".cache",".venv",".phoenix-venv","artifacts","node_modules"):
                raise SystemExit("Blocked sensitive/generated path in index: "+name)
            result=subprocess.run(git+["show",":"+name],capture_output=True)
            if result.returncode==0:
                contents.append((name,result.stdout.decode("utf-8-sig",errors="replace")))
    findings=[]
    for name,content in contents:
        for label,pattern in PATTERNS:
            for match in pattern.finditer(content):
                # Exclude documented placeholder values, never actual credential matches.
                if label=="assigned credential" and match.group(1) in ("your-api-key-here","placeholder-only"):
                    continue
                line=content.count("\n",0,match.start())+1
                findings.append(f"{name}:{line}: possible {label}")
    if findings:
        print("\n".join(findings))
        raise SystemExit(1)
    print(f"Secret scan passed: {len(contents)} source/index files; no secret values printed")


if __name__=="__main__":
    main()
