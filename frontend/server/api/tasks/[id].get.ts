export default defineApiHandler((event, graphql) => loadTask(graphql, getRouterParam(event, 'id')))
