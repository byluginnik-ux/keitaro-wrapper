export default defineApiHandler((event, graphql) =>
  runStreamAction(graphql, 'unpin', {
    streamId: getRouterParam(event, 'id'),
    offerId: getRouterParam(event, 'offerId'),
  }),
)
