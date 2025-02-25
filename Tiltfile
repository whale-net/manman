load('ext://namespace', 'namespace_create')
# appending '-dev' just in case this is ever ran from prod cluster
namespace = 'manman-dev'
namespace_create(namespace)

load('ext://dotenv', 'dotenv')
# load env vars from .env
dotenv()

# load the dev-util helm chart museum
load('ext://helm_resource', 'helm_resource', 'helm_repo')
helm_repo('dev-util', 'https://whale-net.github.io/dev-util')

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


# create manman app
docker_build(
    'manman',
    context='.'
)
# k8s_yaml(
#     helm(
#         'charts/manman-host',
#         name='manman-host',
#         namespace=namespace,
#         set=[
#             'image.name=manman',
#            'image.tag=dev',
#            'env.db.url={}'.format(os.getenv('DATABASE_URL')),
#            'namespace={}'.format(namespace)
#        ]
#    )
#)

# this should be a docker compose becauset hat is how I will actually deploy it
#local_resource(
#    name='manman-worker',
#    cmd='docker run -d --name manman_worker manman:dev',
#    resource_deps=['manman']
#)
