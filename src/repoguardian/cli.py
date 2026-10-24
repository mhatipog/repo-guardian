"""Local command-line interface to Repo Guardian (no private controller required)."""
import argparse
import json
import os
import sys

from .controller import Control, Refused, OWNER, parse_intent, safe_repo


def make_parser():
    parser = argparse.ArgumentParser(
        prog="repo-guardian",
        description="GitHub repositories, topics, forks and visibility — CLI or ChatGPT controller")
    commands = parser.add_subparsers(dest="command", required=True)
    ins = commands.add_parser("inspect", help="Read a repository's ID, visibility and fork status")
    ins.add_argument("repo")
    create = commands.add_parser("create", help="Create a new personal repository")
    create.add_argument("name")
    create.add_argument("--visibility", choices=("private", "public"), default="private")
    create.add_argument("--description", default="")
    fk = commands.add_parser("fork", help="Create a GitHub fork (public sources remain public)")
    fk.add_argument("source")
    fk.add_argument("--name", required=True)
    cp = commands.add_parser("private-copy", help="Clone a public Git repo into a private standalone repo")
    cp.add_argument("source")
    cp.add_argument("--name", required=True)
    tp = commands.add_parser("topics", help="Add, remove or replace GitHub topics")
    tp.add_argument("repo")
    tp.add_argument("names", nargs="*")
    tp.add_argument("--mode", choices=("add", "remove", "replace"), default="add")
    vis = commands.add_parser("visibility", help="Switch visibility of a standalone repository")
    vis.add_argument("repo")
    vis.add_argument("target", choices=("private", "public"))
    runner = commands.add_parser("execute-json", help="Execute a single strict Repo Guardian JSON command")
    runner.add_argument("--request", default=None, help="JSON object (or set RG_REQUEST env)")
    return parser


def prepare_request(args, controller):
    if args.command == "inspect":
        repo = safe_repo(args.repo)
        data = controller.admin("GET", "/repos/" + repo)
        return {"repo": data.get("full_name"), "id": data.get("id"),
                "visibility": data.get("visibility"), "fork": data.get("fork"),
                "default_branch": data.get("default_branch"),
                "archived": data.get("archived")}
    if args.command == "create":
        return {"version": 1, "action": "create_repo", "name": args.name,
                "description": args.description, "visibility": args.visibility}
    if args.command == "fork":
        return {"version": 1, "action": "fork", "source": args.source, "name": args.name}
    if args.command == "private-copy":
        return {"version": 1, "action": "private_copy", "source": args.source,
                "name": args.name}
    if args.command == "topics":
        return {"version": 1, "action": "topics", "repo": args.repo,
                "names": args.names, "mode": args.mode}
    if args.command == "visibility":
        repo = safe_repo(args.repo)
        data = controller.admin("GET", "/repos/" + repo)
        if data.get("visibility") == args.target:
            return {"unchanged": True, "repo": repo, "visibility": args.target}
        return {"version": 1, "action": "visibility", "repo": repo,
                "visibility": args.target, "expected_repo_id": data.get("id"),
                "expected_visibility": data.get("visibility"),
                **({"acknowledge_public_exposure": True}
                   if args.target == "public" else {})}
    if args.command == "execute-json":
        raw = args.request or os.environ.get("RG_REQUEST")
        if not raw or len(raw) > 8192:
            raise Refused("Provide RG_REQUEST JSON (max 8192 characters)")
        return parse_intent(raw)
    raise Refused("Unknown command")


def main(argv=None):
    args = make_parser().parse_args(argv)
    token = os.getenv("RG_ADMIN_TOKEN") or os.getenv("GH_TOKEN")
    if not token:
        print("RG_ADMIN_TOKEN or GH_TOKEN environment variable is required", file=sys.stderr)
        return 2
    try:
        controller = Control("cli-local-only", token)
        request = prepare_request(args, controller)
        if isinstance(request, dict) and ("unchanged" in request or args.command == "inspect"):
            print(json.dumps(request, sort_keys=True))
            return 0
        value = parse_intent(json.dumps(request))
        if value["action"] == "status":
            print("CLI ready: a token was supplied (API permissions not verified).")
            return 0
        print(controller.execute(value))
        return 0
    except Refused as e:
        print("Repo Guardian: " + str(e), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
