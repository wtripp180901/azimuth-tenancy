import argparse
import jinja2
import os

parser = argparse.ArgumentParser()
parser.add_argument("--type",required=True,choices=['openstack','kubeconfig'])
parser.add_argument("--cred-file",required=True)
parser.add_argument("--name",required=True)
args = parser.parse_args()

base_dir = os.path.dirname(__file__)
templates_dir = os.path.join(base_dir, "templates")
tenancies_dir = os.path.join(base_dir, "../tenancies")

with open(args.cred_file, 'r') as file:
    cred_data = file.read()

jinja_vars = dict(
    name=args.name,
    tenancyType=args.type,
    cred_data=cred_data
)

environment = jinja2.Environment(loader=jinja2.FileSystemLoader(templates_dir))

tenancy_dir = os.path.join(tenancies_dir, args.name)
os.mkdir(tenancy_dir)

template_files = os.listdir(templates_dir)
if args.type == "openstack":
    template_files.remove("kubeconfig-secret.yaml.j2")
    jinja_vars["cred_sealed_secret_file"] = "appcred-secret-sealed.yaml"
else:
    template_files.remove("appcred-secret.yaml.j2")
    jinja_vars["cred_sealed_secret_file"] = "kubeconfig-secret-sealed.yaml"

for t in template_files:
    namespace_template = environment.get_template(t)
    content = namespace_template.render(jinja_vars)
    with open(os.path.join(tenancy_dir,t).replace(".j2",""), mode="w", encoding="utf-8") as outputFile:
        outputFile.write(content)

with open(os.path.join(tenancies_dir,"kustomization.yaml"),'a') as resourcesFile:
    resourcesFile.write("  - ./"+args.name+"\n")
