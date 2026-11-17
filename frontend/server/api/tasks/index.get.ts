export default defineApiHandler((event, graphql) => loadTasks(graphql, getQuery(event)))
