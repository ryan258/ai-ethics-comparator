ryanjohnson@MacBookAir ai-ethics-comparator % npm run dev

> ai-ethics-comparator@5.0.0 dev
> nodemon server.js

[nodemon] 3.1.10
[nodemon] to restart at any time, enter `rs`
[nodemon] watching path(s): *.*
[nodemon] watching extensions: js,mjs,cjs,json
[nodemon] starting `node server.js`
[dotenv@17.2.3] injecting env (2) from .env -- tip: ⚙️  load multiple .env files with { path: ['.env.local', '.env'] }
/Users/ryanjohnson/dev/ai-ethics-comparator/server.js:16
const limit = pLimit(3); // Max 3 concurrent requests
              ^

TypeError: pLimit is not a function
    at Object.<anonymous> (/Users/ryanjohnson/dev/ai-ethics-comparator/server.js:16:15)
    at Module._compile (node:internal/modules/cjs/loader:1521:14)
    at Module._extensions..js (node:internal/modules/cjs/loader:1623:10)
    at Module.load (node:internal/modules/cjs/loader:1266:32)
    at Module._load (node:internal/modules/cjs/loader:1091:12)
    at Function.executeUserEntryPoint [as runMain] (node:internal/modules/run_main:164:12)
    at node:internal/main/run_main_module:28:49

Node.js v20.19.5
[nodemon] app crashed - waiting for file changes before starting...