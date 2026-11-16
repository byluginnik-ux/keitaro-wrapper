export default defineApiHandler((event, graphql) => loadEditor(graphql, getRouterParam(event, 'id')))
