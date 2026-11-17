export default defineApiHandler(async (event, graphql) =>
  runStreamAction(graphql, 'add', { streamId: getRouterParam(event, 'id'), version: getQuery(event).version, body: await readBody(event) }),
)
