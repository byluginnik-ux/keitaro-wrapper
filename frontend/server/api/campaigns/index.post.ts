export default defineApiHandler(async (event, graphql) => createCampaign(graphql, await readBody(event)))
