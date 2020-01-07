import sys
import time

import paramiko

CONN_RETRIES = 30


def _connect(host, user, password):
    i = 1
    while True:
        print("Trying to connect to {} ({}/{})".format(host, i, CONN_RETRIES))

        try:
            ssh_client = paramiko.SSHClient()
            ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh_client.connect(host, 22, username=user, password=password)
            print("Connected to {}".format(host))
            break
        except paramiko.AuthenticationException:
            print("Authentication failed when connecting to {}".format(host))
            sys.exit(1)
        except:
            print("Could not SSH to {}, waiting for it to start".format(host))
            i += 1
            time.sleep(2)

        # If we could not connect within time limit
        if i == CONN_RETRIES:
            print("Could not connect to {}. Giving up".format(host))
            sys.exit(1)

    sftp_client = ssh_client.open_sftp()
    return ssh_client, sftp_client


class RemoteInterface:
    def __init__(self, host, user, password):
        self.host = host
        self.user = user
        self.password = password
        self.pids_2_kill = []

    def __enter__(self):
        self.ssh, self.sftp = _connect(self.host, self.user, self.password)
        return self

    def do_command(self, command_str, pkill_on_exit=False, stdout_thru=False):
        command = 'echo $$; exec ' + command_str
        stdin, stdout, stderr = self.ssh.exec_command(command)
        pid = int(stdout.readline())  # first line is pid
        if pkill_on_exit:
            self.pids_2_kill.append(pid)

        if stdout_thru:
            while True:
                line = stdout.readline().rstrip('\n')
                # eline = stderr.readline().rstrip('\n')
                if line:
                    print(line)
                    continue
                # if eline:
                #     print('ERR: {}'.format(eline))
                #     continue

                if stdout.channel.exit_status_ready():
                    break

    def upload_file(self, local_path, remote_path):
        self.sftp.put(local_path, remote_path)

    def download_file(self, remote_path, local_path):
        self.sftp.get(remote_path, local_path)

    def __exit__(self, exc_type, exc_val, exc_tb):
        for pid in self.pids_2_kill:
            _stdin, _stdout, _stderr = self.ssh.exec_command('kill {}'.format(pid))
            _stdin, _stdout, _stderr = self.ssh.exec_command('pkill -p {}'.format(pid))
        self.sftp.close()
        self.ssh.close()
