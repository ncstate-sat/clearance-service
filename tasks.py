from invoke import task


@task
def build_image(c):
    registry_name = "satregistry.ehps.ncsu.edu/clearance-tool/clearance-service"
    git_ref = c.run("git rev-parse --short HEAD", hide=True).stdout.strip()
    branch_name = c.run("git rev-parse --abbrev-ref HEAD", hide=True).stdout.strip()
    branch_name = branch_name.replace("/", "-")
    build_date = c.run("date -u +'%Y-%m-%d.%H%MZ'", hide=True).stdout.strip()
    c.run(f"docker build -t {registry_name}:{branch_name}.{git_ref}.{build_date} .")
    c.config["tag"] = f"{registry_name}:{branch_name}.{git_ref}.{build_date}"


@task(build_image)
def push_image(c):
    c.run(f"docker image push {c.config['tag']}")
