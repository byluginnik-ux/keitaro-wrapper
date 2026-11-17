export default defineApiHandler((event, graphql) => cancelTask(graphql, getRouterParam(event, 'id')))
