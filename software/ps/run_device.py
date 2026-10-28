'Select normal or debug. Motion defaults OFF; normal has explicit horizontal opt-in.'
import argparse


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, add_help=False)
    parser.add_argument('--operation', choices=['normal', 'debug'], required=True)
    args, remaining = parser.parse_known_args(argv)
    if args.operation == 'normal':
        from run_normal import main as run
    else:
        from run_buffered import main as run
    return run(remaining)


if __name__ == '__main__':
    raise SystemExit(main())
