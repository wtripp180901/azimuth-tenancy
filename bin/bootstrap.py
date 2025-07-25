import argparse
import jinja2
import os
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument("--type",required=True,choices=['openstack','kubeconfig'])
parser.add_argument("--cred-file",required=True)
parser.add_argument("--name",required=True)
parser.add_argument("--azimuth-kubeconfig",required=True)
parser.add_argument("--git-remote-url",required=True)
parser.add_argument("--oidc-admin-username",required=True)
parser.add_argument("--oidc-admin-email",required=True)
args = parser.parse_args()

base_dir = os.path.dirname(__file__)
templates_dir = os.path.join(base_dir, "templates")
tenancies_dir = os.path.join(base_dir, "../tenancies")

with open(args.cred_file, 'r') as file:
    cred_data = file.read()

jinja_vars = dict(
    name=args.name,
    cred_data=cred_data,
    oidc_admin_username=args.oidc_admin_username,
    oidc_admin_email=args.oidc_admin_email
)

environment = jinja2.Environment(loader=jinja2.FileSystemLoader(templates_dir))

tenancy_dir = os.path.join(tenancies_dir, args.name)
if not os.path.exists(tenancy_dir):
  os.mkdir(tenancy_dir)
  with open(os.path.join(tenancies_dir,"kustomization.yaml"),'a') as resourcesFile:
    resourcesFile.write("  - ./"+args.name+"\n")

cred_secret_file = None
template_files = os.listdir(templates_dir)
if args.type == "openstack":
    template_files.remove("kubeconfig-secret.yaml.j2")
    jinja_vars["cred_sealed_secret_file"] = "appcred-secret-sealed.yaml"
    cred_secret_file = "appcred-secret.yaml"
else:
    template_files.remove("appcred-secret.yaml.j2")
    jinja_vars["cred_sealed_secret_file"] = "kubeconfig-secret-sealed.yaml"
    cred_secret_file = "kubeconfig-secret.yaml"

for t in template_files:
    namespace_template = environment.get_template(t)
    content = namespace_template.render(jinja_vars)
    with open(os.path.join(tenancy_dir,t).replace(".j2",""), mode="w", encoding="utf-8") as outputFile:
        outputFile.write(content)

subprocess.run(["kubeseal",
                "--kubeconfig", args.azimuth_kubeconfig,
                "--controller-namespace", "sealed-secrets-system",
                "--controller-name", "sealed-secrets",
                "--secret-file", "./tenancies/"+args.name+"/"+cred_secret_file,
                "--sealed-secret-file", "./tenancies/"+args.name+"/"+jinja_vars["cred_sealed_secret_file"]])

print("Created tenancy \""+args.name)
print("Commit and push to ("+args.git_remote_url+")? [y/n]")
resp = input()
if resp == "y":
   subprocess.run(["git","add","./tenancies"])
   subprocess.run(["git","commit","-m","Added "+args.name+" tenancy"])
   subprocess.run(["git", "push"])

subprocess.run(["flux", "create", "source", "git", "tenant-config", "--url="+args.git_remote_url, "--branch=main"])
subprocess.run(["flux", "create", "kustomization", "tenant-config", "--source=GitRepository/tenant-config", "--prune=true"])