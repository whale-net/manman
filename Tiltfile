load('ext://namespace', 'namespace_create')
# appending '-dev' just in case this is ever ran from prod cluster
namespace = 'manman-dev'
namespace_create(namespace)

load('ext://dotenv', 'dotenv')
# load env vars from .env
dotenv()

# build_env = os.getenv('MANMAN_BUILD_ENV', 'default') # Old general build env
# print("Build environment:", build_env) # Old print
app_env = os.getenv('APP_ENV', 'dev')

# New specific build environment variables
build_postgres_env = os.getenv('MANMAN_BUILD_POSTGRES_ENV', 'default')
build_rabbitmq_env = os.getenv('MANMAN_BUILD_RABBITMQ_ENV', 'default')
print("Postgres Build Environment:", build_postgres_env)
print("RabbitMQ Build Environment:", build_rabbitmq_env)


# load the dev-util helm chart museum
load('ext://helm_resource', 'helm_resource', 'helm_repo')
helm_repo('dev-util', 'https://whale-net.github.io/dev-util')

# setup nginx ingress controller for local development
helm_repo('ingress-nginx', 'https://kubernetes.github.io/ingress-nginx')
helm_resource('manman-nginx-ingress', 'ingress-nginx/ingress-nginx',
    namespace='ingress-nginx',
    flags=['--create-namespace',
           '--set=controller.service.type=NodePort',
           '--set=controller.hostPort.enabled=true',
           '--set=controller.service.nodePorts.http=30080',
           '--set=controller.service.nodePorts.https=30443',
           '--set=controller.admissionWebhooks.enabled=false',
           '--set=controller.ingressClassResource.name=manman-nginx',
           '--set=controller.ingressClass=manman-nginx']
)

# setup postgres
helm_resource('postgres-dev', 'dev-util/postgres-dev', resource_deps=['dev-util'],
    flags=['--set=postgresDB=manman', '--set=namespace={}'.format(namespace)]
)
k8s_resource(workload='postgres-dev', port_forwards='5432:5432')

# setup rabbitmq
helm_resource('rabbitmq-dev', 'dev-util/rabbitmq-dev', resource_deps=['dev-util'],
    flags=['--set=namespace={}'.format(namespace)]
)
k8s_resource(workload='rabbitmq-dev', port_forwards='5672:5672')
k8s_resource(workload='rabbitmq-dev', port_forwards='15672:15672')


# setup otel collector
helm_resource('otelcollector-dev', 'dev-util/otelcollector-dev', resource_deps=['dev-util'],
    flags=['--set=namespace={}'.format(namespace)]
)
# no need to publicly expose otel collector
#k8s_resource(workload='otelcollector-dev', port_forwards='4317:4317')

# create manman app
docker_build(
    'manman',
    context='.',
    build_args={"COMPILE_CORES": "2"},
    ignore=['.git', 'data', 'dist', '.venv', 'manman.log', 'manman.warnings.log', 'build', 'bin']
)
db_url_default = 'postgresql+psycopg2://postgres:password@postgres-dev.manman-dev.svc.cluster.local:5432/manman'
db_url = db_url_default
if build_postgres_env == 'custom': # Updated condition
    db_url = os.getenv('MANMAN_POSTGRES_URL') or db_url_default

# Control which APIs to deploy in dev (can be overridden with env vars)
enable_experience_api = os.getenv('MANMAN_ENABLE_EXPERIENCE_API', 'true').lower() == 'true'
enable_worker_dal_api = os.getenv('MANMAN_ENABLE_WORKER_DAL_API', 'true').lower() == 'true'
enable_status_api = os.getenv('MANMAN_ENABLE_STATUS_API', 'true').lower() == 'true'

# RabbitMQ connection parameters
rabbitmq_host_default = 'rabbitmq-dev.manman-dev.svc.cluster.local'
rabbitmq_port_default = '5672'
rabbitmq_user_default = 'rabbit'
rabbitmq_password_default = 'password'

# Initialize with defaults
rabbitmq_host = rabbitmq_host_default
rabbitmq_port = rabbitmq_port_default
rabbitmq_user = rabbitmq_user_default
rabbitmq_password = rabbitmq_password_default

if build_rabbitmq_env == 'custom': # Updated condition
    rabbitmq_host = os.getenv('MANMAN_RABBITMQ_HOST') or rabbitmq_host_default
    rabbitmq_port = os.getenv('MANMAN_RABBITMQ_PORT') or rabbitmq_port_default
    rabbitmq_user = os.getenv('MANMAN_RABBITMQ_USER') or rabbitmq_user_default
    rabbitmq_password = os.getenv('MANMAN_RABBITMQ_PASSWORD') or rabbitmq_password_default
# Removed the 'else' block that explicitly set defaults, as they are now initialized before the if block.

# Build the helm set arguments
helm_set_args = [
    'image.name=manman',
    'image.tag=dev',
    'env.db.url={}'.format(db_url),
    'env.rabbitmq.host={}'.format(rabbitmq_host),
    'env.rabbitmq.port={}'.format(rabbitmq_port),
    'env.rabbitmq.user={}'.format(rabbitmq_user),
    'env.rabbitmq.password={}'.format(rabbitmq_password),
    #'env.rabbitmq.enable_ssl=true',
    'env.otelCollector.logs.endpoint=http://otel-collector.{}.svc.cluster.local:4317'.format(namespace),
    'env.otelCollector.traces.endpoint=http://otel-collector.{}.svc.cluster.local:4317'.format(namespace),
    'namespace={}'.format(namespace),
    # for local dev, require manual migration and protect against bad models being used
    'migrations.skip_migration=true',
    # Control which APIs to deploy
    'apis.experience.enabled={}'.format(str(enable_experience_api).lower()),
    'apis.workerDal.enabled={}'.format(str(enable_worker_dal_api).lower()),
    'apis.status.enabled={}'.format(str(enable_status_api).lower()),
    # Enable ingress for local development with auto-generated rules
    'ingress.enabled=true',
    'ingress.ingressClassName=manman-nginx',
]

k8s_yaml(
    helm(
        'charts/manman-host',
        name='manman-host',
        namespace=namespace,
        set=helm_set_args
    )
)

# Note: Ingress controller is available on NodePort 30080
# APIs are auto-routed by Helm chart ingress template:
#   Experience API: http://localhost:30080/experience/
#   Worker DAL API: http://localhost:30080/workerdal/
#   Status API: http://localhost:30080/status/

print("APIs will be available at (auto-generated by Helm chart):")
if enable_experience_api:
    print("  Experience API: http://localhost:30080/experience/")
if enable_worker_dal_api:
    print("  Worker DAL API: http://localhost:30080/workerdal/")
if enable_status_api:
    print("  Status API: http://localhost:30080/status/")

# this should be a docker compose becauset hat is how I will actually deploy it
#local_resource(
#    name='manman-worker',
#    cmd='docker run -d --name manman_worker manman:dev',
#    resource_deps=['manman']
#)
