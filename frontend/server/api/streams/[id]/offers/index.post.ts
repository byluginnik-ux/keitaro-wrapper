export default defineApiHandler(async (event, graphql) =>
  runStreamAction(graphql, 'add', { streamId: getRouterParam(event, 'id'), body: await readBody(event) }),
)
