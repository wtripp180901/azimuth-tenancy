# azimuth-tenant-config  <!-- omit in toc -->

This repository provides a base for configuring the tenancies for an Azimuth instance that is
using [OpenID Connect (OIDC)](https://openid.net/) authentication. This includes support for a
new "apps-only" mode that allows Azimuth to deploy Kubernetes applications onto pre-existing
clusters.

The repository uses [kustomize](https://kustomize.io/) to build the configuration and assumes
that [Flux CD](https://fluxcd.io/) with
[sealed secrets](https://github.com/bitnami-labs/sealed-secrets) will be used to deploy the
configuration on the Azimuth cluster. Familiarity with these tools is assumed, along with
familiarity with the configuration and deployment of Azimuth.

> [!WARNING]
> OIDC authentication and "apps-only" mode are experimental and not fully tested.

## Contents  <!-- omit in toc -->

- [Required tools](#required-tools)
- [Set up Azimuth configuration repository](#set-up-azimuth-configuration-repository)
- [Fork/copy this repository](#forkcopy-this-repository)
- [Sealing secrets](#sealing-secrets)
- [Configuring Flux](#configuring-flux)
- [OpenID Connect (OIDC) authentication](#openid-connect-oidc-authentication)
  - [Configuring Azimuth](#configuring-azimuth)
- [Apps-only mode](#apps-only-mode)
  - [Configuring Azimuth](#configuring-azimuth-1)
  - [Configuring app templates](#configuring-app-templates)
- [Configuring tenancies](#configuring-tenancies)
  - [OpenStack credential](#openstack-credential)
  - [Kubernetes credential](#kubernetes-credential)


## Required tools

This document assumes that following tools are available:

  * [kubectl](https://kubernetes.io/docs/reference/kubectl/)
  * [Flux CLI](https://fluxcd.io/flux/cmd/)
  * [kubeseal](https://github.com/bitnami-labs/sealed-secrets?tab=readme-ov-file#kubeseal)

## Set up Azimuth configuration repository

The changes for both OIDC authentication and "apps-only" mode currently reside in a branch -
[feat/standalone-apps](https://github.com/azimuth-cloud/azimuth-config/tree/feat/standalone-apps) -
which you will need to merge in to your Azimuth configuration repository.

First,
[create an azimuth-config repository](https://azimuth-config.readthedocs.io/en/latest/repository/)
for your Azimuth instance as noraml.

Once you have a repository with a `main` branch set up, merge in the changes from the
`feat/standalone-apps` branch:

```sh
git remote update
git merge upstream/feat/standalone-apps
```

Next,
[create a new environment](https://azimuth-config.readthedocs.io/en/latest/repository/#creating-a-new-environment)
and configure it as single node or HA as usual.

At this point, your Azimuth instance is ready to
[provision](https://azimuth-config.readthedocs.io/en/latest/deployment/), although you may wish
to add additional configuration as described below first.

## Fork/copy this repository

First, create a new blank repository in GitHub (or GitLab, etc.) to get a remote URL.
Then create a copy (i.e. a detached fork) of this repository to contain the tenancy
configuration for your Azimuth instance:

```sh
# Clone the repository
git clone \
  https://github.com/azimuth-cloud/azimuth-tenant-config.git \
  my-azimuth-tenant-config
cd my-azimuth-tenant-config

# Rename the origin remote to upstream so that we can pull changes in future
git remote rename origin upstream

# Add the new origin remote and push the initial commit
git remote add origin <repourl>
git push -u origin main
```

## Sealing secrets

Azimuth includes a deployment of the
[sealed secrets](https://github.com/bitnami-labs/sealed-secrets) controller, allowing sealed
secrets to be safely stored in a tenant config repository and rolled out onto the Azimuth
cluster using Flux CD.

To seal a secret, we must connect to the Azimuth Kubernetes cluster to obtain the
key that should be used to encrypt the data. Azimuth supports doing this by using the
seed node as a SOCKS proxy.

First, run the following in your Azimuth configuration repository:

```sh
# Activate your Azimuth environment
source ./bin/activate my-env

# Start the SOCKS proxy and generate the local kubeconfig file
./bin/kube-connect
```

The output of the `kube-connect` command is a path to a `KUBECONFIG` file that can be used to
connect to the cluster.

We can then use this in a `kubeseal` command to seal a secret in such a way that only the
Azimuth Kubernetes cluster can decrypt it and reveal the data:

```sh
kubeseal \
  --kubeconfig /path/to/kubeconfig \
  --controller-namespace sealed-secrets-system \
  --controller-name sealed-secrets \
  --secret-file ./tenancies/${TENANCY}/{appcred,kubeconfig}-secret.yaml \
  --sealed-secret-file ./tenancies/${TENANCY}/{appcred,kubeconfig}-secret-sealed.yaml
```

The SOCKS proxy can then be closed down:

```sh
./bin/kube-connect --terminate
```

> [!CAUTION]
> You must **never** commit an unsealed secret file to Git.
> 
> There are patterns in `.gitignore` that should ensure this never happens. Be sure to preserve
> those patterns if you make changes to `.gitignore`.
>
> If you do accidentally commit an unsealed secret file to Git, you will need to revoke the
> credentials and issue new credentials before updating and re-sealing the secret.

## Configuring Flux

To configure Flux to use your repository to manage tenancies on your Azimuth cluster, run the
following commands _on the seed node_:

```sh
flux create source git tenant-config --url=<repourl> --branch=main
flux create kustomization tenant-config --source=GitRepository/tenant-config --prune=true
```

This creates a [Kustomization](https://fluxcd.io/flux/components/kustomize/kustomizations/)
in the `flux-system` namespace that will deploy the root `kustomization.yaml` from your
repository, hence deploying all your tenancy namespaces.

## OpenID Connect (OIDC) authentication

When Azimuth is deployed with OIDC authentication, users authenticate with Azimuth using a
realm in the Azimuth-managed Keycloak (which can be federated with other IDPs as required).

Tenancies no longer correspond to projects in OpenStack. Instead, an Azimuth tenancy consists
of a namespace in the Azimuth cluster with a label identifying it as a tenancy namespace, as
in the example [namespace.yaml](./tenancies/example/namespace.yaml)). These namespaces
typically follow the naming convention `az-{tenancy name}`. Secrets containing credentials
are then placed in these namespaces for Azimuth to use when managing platforms.

The tenancies that a user has access to are determined by their membership (or not!) of groups
in the Keycloak realm.

For more information, see
[this documentation page](https://azimuth-config.readthedocs.io/en/feat-identity-diagrams/architecture/identity/).

### Configuring Azimuth

To enable OIDC authentication for Azimuth, add the following variable to your Azimuth config:

```yaml
azimuth_authentication_type: oidc
```

`azimuth-ops` will handle the provisioning of the Keycloak realm and an OIDC client for
Azimuth to use.

## Apps-only mode

When in "apps-only" mode, all functionality in Azimuth that depends on the availability of
a cloud is disabled (e.g. Cluster-as-a-Service, Kubernetes clusters via Cluster API).
Azimuth is only able to deploy apps onto pre-existing Kubernetes clusters and wire up the
services using Zenith.

The Kubernetes clusters onto which apps are deployed are configured by adding secrets containing
[kubeconfig](https://kubernetes.io/docs/concepts/configuration/organize-cluster-access-kubeconfig/)
files to the tenancy namespaces, which Azimuth will then discover. It is currently assumed that
each tenancy will have its own Kubernetes cluster, although these could be
[vClusters](https://www.vcluster.com/) on a single host cluster.

> [!TIP]
> 
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

### Configuring Azimuth

Use following configuration can be used to enable "apps-only" mode for Azimuth:

```yaml
# Enable the null cloud provider
# This cloud provider does not interact with an underlying cloud, but
# does allow apps to be deployed onto pre-existing Kubernetes clusters
azimuth_cloud_provider_type: "null"
```

> [!IMPORTANT]
> `azimuth_cloud_provider_type` must be set to the **string** `"null"` rather than actual `null`.

### Configuring app templates

App templates are configured by adding objects of kind `apptemplates.apps.azimuth-cloud.io`
to the kustomization in the [apptemplates](./apptemplates) directory. Templates for some of
the Azimuth standard apps are configured by default, and can be followed as examples for
adding additional apps.

Make sure to uncomment the `./apptemplates` directory in the root
[kustomization.yaml](./kustomization.yaml) so that the app templates are picked up and provisioned
by Flux.

## Configuring tenancies

To add a new tenancy, first copy [tenancies/example](./tenancies/example) and give the directory
an appropriate name.

Update the `resources` in [tenancies/kustomization.yaml](./tenancies/kustomization.yaml) to
include the new directory.

Update `namespace.yaml` as directed by the comments in the file.

Update/delete the credentials secrets as appropriate (i.e. depending on whether you are targeting
an OpenStack cloud or using "apps-only" mode), and update the `kustomization.yaml` for the tenancy
to reflect which should being used.

### OpenStack credential

If the tenancy is targeting an OpenStack project, create a new application credential for the
target project and download it in `clouds.yaml` format.

Update `appcred-secret.yaml` as directed by the comments in the file before sealing the secret
as described above.

### Kubernetes credential

If Azimuth is in "apps-only" mode, you should already have a `kubeconfig` for the tenancy.

Update `kubeconfig-secret.yaml` as directed by the comments in the file before sealing the secret
as described above.

Commit the new tenancy to the repository and allow Flux to roll it out.
