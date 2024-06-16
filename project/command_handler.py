class CommandHandler:
    def __init__(self, dict: dict):
        self.commands = dict

    def has_command(self, name):
        if name in self.commands.keys():
            return True
        return False

    def get_command(self, name):
        return self.commands[name]

    def add_command(self, name, func):
        self.commands.update(name, func)

    def set_commands(self, dict: dict):
        self.commands = dict