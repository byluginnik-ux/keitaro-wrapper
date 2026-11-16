export default defineApiHandler((event, graphql) =>
  runStreamAction(graphql, 'restore', {
    streamId: getRouterParam(event, 'id'),
    offerId: getRouterParam(event, 'offerId'),
  }),
)
