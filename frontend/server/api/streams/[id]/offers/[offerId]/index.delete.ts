export default defineApiHandler((event, graphql) =>
  runStreamAction(graphql, 'remove', {
    streamId: getRouterParam(event, 'id'),
    offerId: getRouterParam(event, 'offerId'),
  }),
)
