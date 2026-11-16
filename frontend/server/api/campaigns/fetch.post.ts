export default defineApiHandler(async (event, graphql) => fetchStreams(graphql, await readBody(event)))
