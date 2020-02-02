import os
import json
import sublime
import sublime_plugin

class PathSwapCommand(sublime_plugin.TextCommand):

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)
        settings = sublime.load_settings('PathSwap.sublime-settings')

        if settings.has("custom"):
            self.custom_win_linux_map = settings.get("custom")
            self.custom_linux_win_map = {v:k for k,v in self.custom_win_linux_map.items()}

            self.custom_drives = set(self.custom_win_linux_map.keys())
            self.custom_paths = list(self.custom_linux_win_map.keys())

        else:
            self.custom_win_linux_map = {}
            self.custom_linux_win_map = {}
            self.custom_drives = set()
            self.custom_paths = []

    @staticmethod
    def classify_path(text):
        """
        Classifies if the text is a Windows path or a Linux path.

        A path is determined to be a Linux path if it starts with a "/".
        Currently, this only classifies absolute paths. Results may not be
        accurate for non-absolute paths. The text variable must start and end
        with single or double quotes.
        """

        ## Since text[0], text[-1] are either single or double quotes, we
        ## check text[1]
        if text[1] == '/':
            return "linux"
        else:
            return "windows"

    def convert_windows_to_linux(self, text):
        """
        Converts a windows path to a linux path.
        """
        ## Since the user may have either manually escaped slashes or
        ## used raw-strings, we will replace both instances.
        text = text.replace('\\\\', '/')
        text = text.replace('\\', '/')

        ## Getting length of the drive letter.
        for idx, char in enumerate(text):
            if char == ':':
                break

        drive = text[1: idx] + ':'

        if drive in self.custom_drives:
            text = text[0] + self.custom_win_linux_map[drive] + text[idx+1:]
        else:
            text = text[0] + '/mnt/%s' % text[1: idx].lower() + text[idx+1:]

        return text

    def convert_linux_to_windows(self, text):
        """
        Converts a linux path to a windows path.
        """
        custom_match_found = False

        for custom_path in self.custom_paths:
            if len(custom_path) < len(text) and text[1: len(custom_path)+1] == custom_path:
                drive = self.custom_linux_win_map[text[1: len(custom_path)+1]]
                custom_match_found = True

        if not custom_match_found:

            ## If custom math is not found, we assume "/mnt/{DRIVE}" format.
            text = text[0] + text[6:]

            ## Getting length of the drive letter.
            for idx, char in enumerate(text):
                if char == '/':
                    break

            drive = text[1: idx].upper() + ':'
            text = text[0] + drive + text[idx:]

        elif custom_match_found:
            text = text[0] + drive + text[(len(custom_path)+1): ]

        text = text.replace('/', '\\')
        
        return text

    def check_for_raw_string(self, region):
        """
        Checks if the extracted string is a raw string.
        """
        start, end = eval(str(region))
        char = self.view.substr(sublime.Region(start - 1, start))

        if char == 'r':
            return True
        else:
            return False

    def get_string_location(self, text, cursor):
        """
        If the cursor is placed inside a sting, this function returns
        the location of the string. Else, it returns None.
        """
        stack = None
        cursor_is_inside = False
        start_idx, end_idx = None, None
        
        for idx, char in enumerate(text):
            if char == "'" or char == '"':
                if stack is None:
                    stack = (idx, char)
                else:
                    if stack[1] == char:
                        if cursor > stack[0] and cursor < idx+1:
                            cursor_is_inside = True
                            start_idx, end_idx = stack[0], idx + 1
                        stack = None

            if cursor_is_inside:
                break

        return start_idx, end_idx
        
    def run(self, edit):
        """
        Master function that will be called by sublime text.

        Note:
            ridx    :   Region Index
            sidx    :   String Index
            region  :   sublime.Region
        """
        ## Gets the regions of all cursors.
        cursors = self.view.sel()

        for cursor_ridx in cursors:
            line_ridx = self.view.line(cursor_ridx)
            text = self.view.substr(line_ridx)

            line_start_ridx = eval(str(line_ridx))[0]
            cursor_start_ridx = eval(str(cursor_ridx))[0]
            cursor_start_sidx = cursor_start_ridx - line_start_ridx

            path_sidx = self.get_string_location(text, cursor_start_sidx)

            if path_sidx[0] is not None:
                path_ridx = path_sidx[0] + line_start_ridx, \
                            path_sidx[1] + line_start_ridx

                string_region = sublime.Region(*path_ridx)

                extracted_path = self.view.substr(string_region)
                path_type = self.classify_path(extracted_path)

                if path_type == 'linux':
                    converted_path = self.convert_linux_to_windows(extracted_path)
                    is_raw = self.check_for_raw_string(string_region)

                    if is_raw:
                        self.view.replace(edit, string_region, converted_path)
                    else:
                        self.view.replace(edit, string_region, 'r' + converted_path)

                elif path_type == 'windows':
                    converted_path = self.convert_windows_to_linux(extracted_path)
                    self.view.replace(edit, string_region, converted_path)
