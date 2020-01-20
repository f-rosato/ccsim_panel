import fabric

CONN_RETRIES = 30


class RemoteInterface:
    def __init__(self, host, port, user, password):
        self.host = host
        self.user = user
        self.port = port
        self.password = password

    def __enter__(self):
        self.c = fabric.Connection(host=self.host,
                              user=self.user,
                              port=self.port,
                              connect_kwargs={"password": self.password})
        return self

    def do_command(self, command_str, background=False):
        if background:
            command_str = 'nohup {} >& /dev/null &'.format(command_str)
        self.c.run(command_str, pty=not background)

    def upload_file(self, local_path, remote_path):
        self.c.put(local_path, remote_path)

    def download_file(self, remote_path, local_path):
        self.c.get(remote_path, local_path)

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.c.close()
