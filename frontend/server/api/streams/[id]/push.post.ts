export default defineApiHandler(async (event, graphql) =>
  publishStream(graphql, {
    streamId: getRouterParam(event, 'id'),
    version: getQuery(event).version,
    body: await readBody(event),
  }),
)
