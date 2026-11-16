export default defineApiHandler((event, graphql) => searchOffers(graphql, getQuery(event)))
