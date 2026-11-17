export default defineApiHandler((event, graphql) =>
  runStreamAction(graphql, 'cancel', { streamId: getRouterParam(event, 'id'), version: getQuery(event).version }),
)
