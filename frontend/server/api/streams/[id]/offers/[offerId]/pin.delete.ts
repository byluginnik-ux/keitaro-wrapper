export default defineApiHandler((event, graphql) =>
  runStreamAction(graphql, 'unpin', {
    streamId: getRouterParam(event, 'id'), version: getQuery(event).version,
    offerId: getRouterParam(event, 'offerId'),
  }),
)
