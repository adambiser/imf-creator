#!/usr/bin/python3
# -*- coding: utf-8 -*-

import argparse
import imfcreator

_DEFAULT_BANKS = ["genmidi/GENMIDI.OP2"]


class FileTypeHelpFormatter(argparse.RawDescriptionHelpFormatter):
    """For filetype help, don't show usage or the 'help' argument."""
    def add_usage(self, usage, actions, groups, prefix=None):
        pass

    def add_argument(self, action: argparse.Action) -> None:
        if action.dest != "help":
            super().add_argument(action)


# noinspection PyProtectedMember
class HelpFormatter(argparse.RawDescriptionHelpFormatter):
    """A combination of argparse.RawDescriptionHelpFormatter and ArgumentDefaultsHelpFormatter."""
    _get_help_string = argparse.ArgumentDefaultsHelpFormatter._get_help_string

    def add_argument(self, action):
        # noinspection PyUnresolvedReferences
        if isinstance(action, argparse._SubParsersAction):
            # self._add_item(self._format_text, [action.metavar])
            # self._indent()
            # noinspection PyUnresolvedReferences
            for choice_action in action._choices_actions:
                # print(choice_action)
                argparse.HelpFormatter.add_argument(self, choice_action)
                # noinspection PyUnresolvedReferences
                subparser = action.choices[choice_action.dest]
                formatter = subparser._get_formatter()
                # usage
                # formatter.add_usage(subparser.usage, subparser._actions, subparser._mutually_exclusive_groups)
                # description
                # formatter.add_text(subparser.description)
                # positionals, optionals and user-defined groups
                formatter._indent()
                for action_group in subparser._action_groups:
                    formatter.start_section(action_group.title)
                    formatter.add_text(action_group.description)
                    formatter.add_arguments(action_group._group_actions)
                    formatter.end_section()
                formatter._dedent()
                # epilog
                # formatter.add_text(subparser.epilog)
                self.add_text(formatter.format_help())
            # self._dedent()
        else:
            argparse.HelpFormatter.add_argument(self, action)


def main():
    logging_parser = argparse.ArgumentParser(add_help=False)
    logging_parser.add_argument("-v", "--verbose", metavar="level", nargs="?", type=int, default=2,
                                choices=[1, 2, 3, 4], help="Logging verbosity.  1=DEBUG, 2=INFO, 3=WARNING, 4=ERROR")
    # Pre-parse to get the logger level.
    args, _ = logging_parser.parse_known_args()
    imfcreator.logging.getLogger().setLevel(args.verbose * 10)
    # These can be imported now that the logger level has been set.
    import imfcreator.instruments as instruments
    from imfcreator.plugins import AdlibSongFile, MidiSongFile, load_plugins
    load_plugins()
    # noinspection PyTypeChecker
    parser = argparse.ArgumentParser(description="A tool to convert MIDI music files to IMF files.",
                                     formatter_class=HelpFormatter, parents=[logging_parser])
    parser.add_argument("infile", type=str, help="The input file path.")
    parser.add_argument("-o", "--outfile", type=str, help="The output file.")
    parser.add_argument("-b", "--banks", nargs="*", metavar="BANKFILE", type=str, default=_DEFAULT_BANKS,
                        help="Sound banks to load.")
    parser.add_argument("-gm2", "--gm2drummapping", action="store_true",
                        help="Enables GM2 drum mapping when GM2 drum instruments are not defined in banks.")
    # Add file types as subparsers
    subparsers = parser.add_subparsers(title="output file types", dest="type", metavar="filetype")
    for info in AdlibSongFile.get_filetypes():
        subparser = subparsers.add_parser(info.name, description=info.description, help=info.description,
                                          formatter_class=FileTypeHelpFormatter)
        group = subparser.add_argument_group(f"settings")
        for setting in AdlibSongFile.get_filetype_settings(info.name):
            group.add_argument(f"--{setting.name}", help=setting.description, **setting.kwargs)
    parser.set_defaults(type="imf1")
    # parser.print_help()
    args = parser.parse_args()
    # print(args)
    instruments.ENABLE_GM2_DRUM_NOTE_MAPPING = args.gm2drummapping
    # Process args
    for bank in args.banks:
        instruments.add_file(bank)
    settings = {}
    midi_song = MidiSongFile.load_file(args.infile)
    adlib_song = AdlibSongFile.convert_from(midi_song, args.type, settings)
    adlib_song.save_file(args.outfile)


if __name__ == "__main__":
    main()
