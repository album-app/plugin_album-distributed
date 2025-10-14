from album.distributed import distributed_modes


def create_run_distributed_parser(parser):
    p = parser.create_command_parser('run-distributed', distributed_modes.run, 'Run a solution in batch mode.')
    p.add_argument('solution', type=str, help='Path for the solution file or coordinates of the solution '
                                              '(catalog:group:name:version).')
    p.add_argument('--mode', type=str, required=False, default="basic",
                   help='Mode describing how to run the solution repeatedly. '
                        'Current choices: %s' % " ".join(distributed_modes.get_run_mode_choices()))
    p.add_argument(
        '--dry-run',
        required=False,
        help='Parameter to indicate a dry run and only show what would happen.',
        action='store_true'
    )
    p.add_argument('--threads', type=int, required=False, default=3,
                   help='(mode queue only) Number of threads to spawn for processing the task queue.')
