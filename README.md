# azimuth-apps-config

This repository provides a base for configuring an Azimuth instance deployed in "apps-only" mode.

> [!WARNING]
> Azimuth's "apps-only" mode is experimental and not fully tested.

When in "apps-only" mode, all functionality in Azimuth that depends on the availability of a cloud
is disabled (e.g. Cluster-as-a-Service, Kubernetes clusters via Cluster API). Azimuth is only
able to deploy apps onto pre-existing Kubernetes clusters and wire up the services using Zenith.

The Kubernetes clusters onto which apps are deployed are configured by adding secrets containing
[kubeconfig](https://kubernetes.io/docs/concepts/configuration/organize-cluster-access-kubeconfig/)
files to the tenancy namespaces, which Azimuth will then discover. It is currently assumed that
each tenancy will have its own Kubernetes cluster, although these could be
[vClusters](https://www.vcluster.com/) on a single host cluster.

This repository uses [kustomize](https://kustomize.io/) to build the configuration and
[Flux CD](https://fluxcd.io/) with [sealed secrets](https://github.com/bitnami-labs/sealed-secrets)
to deploy the configuration on the Azimuth cluster. Familiarity with these tools is assumed, along
with familiarity with the configuration and deployment of Azimuth.

> [!TIP]
> Management of per-tenant clusters is not in the scope of either Azimuth or this repository.
>
> Azimuth has no opinion on where the kubeconfigs that it uses come from as long as it is able to 
> reach the Kubernetes API for those clusters.
>
> The expected pattern is to have a "workload" cluster that is separate to the Azimuth cluster
> and contains a vCluster for each tenant, managed via GitOps (e.g. Flux). The kubeconfigs for
> those vClusters will then be dropped into the tenancy configurations in this repository.
>
> The following repositories may be of interest when implementing this pattern:
>
>   * [stackhpc/capi-helm-fluxcd-config](https://github.com/stackhpc/capi-helm-fluxcd-config)
>     for the host cluster, using Cluster API and OpenStack
>   * [stackhpc/vcluster-fluxcd-config](https://github.com/stackhpc/vcluster-fluxcd-config)
>     for the vClusters

## Tools

This document assumes that following tools are available:

  * [kubectl](https://kubernetes.io/docs/reference/kubectl/)
  * [Flux CLI](https://fluxcd.io/flux/cmd/)
  * [kubeseal](https://github.com/bitnami-labs/sealed-secrets?tab=readme-ov-file#kubeseal)

## Azimuth configuration

To use Azimuth in "apps-only" mode, first
[create an azimuth-config repository](https://azimuth-config.readthedocs.io/en/latest/repository/)
for your Azimuth instance.

Once you have a repository with a `main` branch set up, merge in the changes from the
[feat/standalone-apps](https://github.com/azimuth-cloud/azimuth-config/tree/feat/standalone-apps)
branch:

```sh
git remote update
git merge upstream/feat/standalone-apps
```

Next,
[create a new environment](https://azimuth-config.readthedocs.io/en/latest/repository/#creating-a-new-environment)
and configure it as single node or HA as usual.

> [!NOTE]
> Even though Azimuth is being deployed in "apps-only" mode, `azimuth-ops` currently still assumes
> the presence of an OpenStack cloud into which the Azimuth instance will be deployed.

Add the following configuration to the environment to disable all the cloud-based functionality
and leave only the Kubernetes apps functionality:

```yaml
azimuth_cloud_provider_type: "null"
```

> [!IMPORTANT]
> This variable must be set to the **string** `"null"` rather than actual `null`.

Then
[provision your Azimuth instance](https://azimuth-config.readthedocs.io/en/latest/deployment/)
as usual.

### Exporting the sealed secrets certificate

Because an Azimuth installation does not support directly connecting to the Kubernetes API
for the Azimuth cluster, in either single-node or HA configurations, we must export the
certificate that is used for sealing secrets so that we can use it later.

To do this, run the following commands in your **Azimuth config directory**:

```sh
# Activate your apps-only environment
source ./bin/activate my-env

# Connect to the Azimuth Kubernetes cluster via a SOCKS proxy
eval $(./bin/kube-connect)

# Extract the certificate to a file
kubeseal \
  --fetch-cert \
  --controller-namespace sealed-secrets-system \
  --controller-name sealed-secrets \
  > /path/to/cert

# Shut down the Kubernetes connection
./bin/kube-connect --terminate
```

## Fork/copy this repository

First, create a new blank repository in GitHub (or GitLab, etc.) to get a remote URL.
Then create a copy (i.e. a detached fork) of this repository to contain the app templates
and tenancy configuration for your Azimuth instance:

```sh
# Clone the repository
git clone https://github.com/azimuth-cloud/azimuth-apps-config.git my-azimuth-apps-config
cd my-azimuth-apps-config

# Rename the origin remote to upstream so that we can pull changes in future
git remote rename origin upstream

# Add the new origin remote and push the initial commit
git remote add origin <repourl>
git push -u origin main
```

## Configuring app templates

App templates are configured by adding objects of kind `apptemplates.apps.azimuth-cloud.io`
to the kustomization in the [apptemplates](./apptemplates) directory. Templates for some of
the Azimuth standard apps are configured by default, and can be followed as examples for
adding additional apps.

## Configuring tenancies

When Azimuth is deployed in "apps-only" mode, an Azimuth tenancy consists of a namespace in the
Azimuth cluster with a name of the form `az-{tenancy name}`. This namespace contains a secret
with a default kubeconfig to use for deploying apps.

To add a new tenancy, first copy [tenancies/example](./tenancies/example) and give it an
appropriate name.

Update the resources in [tenancies/kustomization.yaml](./tenancies/kustomization.yaml) to
include the new directory.

Update the `namespace` in `kustomization.yaml` and `metadata.name` in `namespace.yaml` so that
they reflect the name of the tenancy.

Finally, add the kubeconfig for the tenancy to `kubeconfig-secret.yaml` and seal it using the
certificate we obtained earlier:

```sh
kubeseal \
  --cert /path/to/cert \
  --secret-file ./tenancies/$TENANCY/kubeconfig-secret.yaml \
  --sealed-secret-file ./tenancies/$TENANCY/kubeconfig-secret-sealed.yaml
```

> [!CAUTION]
> You must **never** commit the unsealed `kubeconfig-secret.yaml` to Git.
> 
> There is a pattern in `.gitignore` that should ensure this never happens. Be sure to preserve
> that pattern if you make changes to `.gitignore`.
>
> If you do accidentally commit an unsealed `kubeconfig-secret.yaml` to Git, you will need to
> revoke the credentials and issue new credentials before updating and re-sealing the secret.

## Configuring Flux

To configure Flux to use your repository to manage app templates and tenancies on your
Azimuth cluster, run the following commands _on the seed node_:

```sh
flux create source git apps-config --url=<repourl> --branch=main
flux create kustomization apps-config --source=GitRepository/apps-config --prune=true
```

This creates a [Kustomization](https://fluxcd.io/flux/components/kustomize/kustomizations/)
in the `flux-system` namespace that will deploy the root `kustomization.yaml` from your
repository, hence deploying all your apps and tenancy namespaces.
