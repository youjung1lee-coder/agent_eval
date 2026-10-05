import argparse
import json
import os


def main():
    from dotenv import load_dotenv
    load_dotenv()
    parser = argparse.ArgumentParser(description="GAIA evaluation lifecycle")
    parser.add_argument("--data-dir", default=os.getenv("EVAL_DATA_DIR", "data"))
    sub = parser.add_subparsers(dest="command", required=True)
    reg = sub.add_parser("register")
    reg.add_argument("--agent-path", required=True)
    serve = sub.add_parser("serve")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--host", default="127.0.0.1", choices=["127.0.0.1", "localhost"])
    execute = sub.add_parser("execute")
    execute.add_argument("agent_id")
    execute.add_argument("input")
    gen = sub.add_parser("generate")
    gen.add_argument("agent_id")
    args = parser.parse_args()
    from evaluation_platform.service import Platform
    platform = Platform(args.data_dir)
    if args.command == "serve":
        import uvicorn
        from evaluation_platform.api.app import create_app
        uvicorn.run(create_app(platform), host=args.host, port=args.port)
    elif args.command == "register":
        print(json.dumps(platform.register(args.agent_path), ensure_ascii=False, indent=2))
    elif args.command == "execute":
        print(platform.execute(args.agent_id, args.input).model_dump_json(indent=2))
    else:
        print(json.dumps(platform.generate(args.agent_id), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
