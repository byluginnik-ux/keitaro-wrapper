export default defineApiHandler((event, graphql) =>
  publishStream(graphql, { streamId: getRouterParam(event, 'id'), version: getQuery(event).version }),
)
