PLease look at the [@reit-hauptflow.json](file:///home/nikita/Projects/AICO/backend/src/seeds/data/flows/reit-hauptflow.json) and how we can actually run and test it with the @test-flow.ts script . Now please run the flow, identify miconfigurations, read the accoridng executor and schema definition, modify either them or the flow. Make the flow work perfectly constatnly looking up and validating. Our goal is to have a flow like [@flow.mermaid](file:///home/nikita/Projects/AICO/docs/reference/Reit/flow.mermaid)

The backend is hot reloading, changes apply instantly, however, we need to run 'make rebootstrap' (wait 5s to till backend starts) everytime we change the flow seed file. If there is a missnig feature in the core notify the User about it. If there is a bug / the validator didn't catcha bug, investigate why and notify teh User.

You can look at the logging.json (file:///home/nikita/Projects/AICO/backend/src/seeds/data/logging/logging.json) to see how to enable logging for a single module / filter better for debugging purposes.

You can look at backend logs by running 'make backend-logs-list'

The first thing you do is understand our abckend API and Flow routes to be able to efficiently query, send messages and read flow state / repsonses

Also use the backends validate-cli.ts (it's also not 100% correct all the time, so consider fixin it), you have to always evaluate wich part is actually broken, get to the bottom of it. 