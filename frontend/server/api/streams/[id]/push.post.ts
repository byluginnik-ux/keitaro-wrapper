export default defineApiHandler((event, graphql) =>
  runStreamAction(graphql, 'push', { streamId: getRouterParam(event, 'id') }),
)
