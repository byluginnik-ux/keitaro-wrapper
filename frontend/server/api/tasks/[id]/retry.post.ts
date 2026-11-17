export default defineApiHandler(async (event, graphql) =>
  retryTask(graphql, getRouterParam(event, 'id'), await readBody(event)),
)
