export default defineApiHandler(async (event, graphql) =>
  runStreamAction(graphql, 'pin', {
    streamId: getRouterParam(event, 'id'), version: getQuery(event).version,
    offerId: getRouterParam(event, 'offerId'),
    body: await readBody(event),
  }),
)
