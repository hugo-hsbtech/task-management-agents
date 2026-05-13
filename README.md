# Repository Coverage

[Full report](https://htmlpreview.github.io/?https://github.com/hugo-hsbtech/task-management-agents/blob/python-coverage-comment-action-data/htmlcov/index.html)

| Name                                            |    Stmts |     Miss |   Cover |   Missing |
|------------------------------------------------ | -------: | -------: | ------: | --------: |
| src/backlog/\_\_init\_\_.py                     |        0 |        0 |    100% |           |
| src/backlog/agent.py                            |       89 |        0 |    100% |           |
| src/backlog/contracts.py                        |       48 |        0 |    100% |           |
| src/backlog/platforms/\_\_init\_\_.py           |        4 |        0 |    100% |           |
| src/backlog/platforms/base.py                   |       12 |        0 |    100% |           |
| src/backlog/platforms/linear.py                 |      169 |       20 |     88% |99-100, 128-135, 145-146, 150-151, 360-369 |
| src/backlog/prompts.py                          |        2 |        0 |    100% |           |
| src/backlog/providers/\_\_init\_\_.py           |        0 |        0 |    100% |           |
| src/hsb/\_\_init\_\_.py                         |        0 |        0 |    100% |           |
| src/hsb/agents/\_\_init\_\_.py                  |        0 |        0 |    100% |           |
| src/hsb/agents/\_sdk\_options.py                |       95 |        0 |    100% |           |
| src/hsb/agents/backlog\_agent.py                |       63 |        0 |    100% |           |
| src/hsb/agents/builder\_agent.py                |       47 |       33 |     30% |70-131, 138 |
| src/hsb/agents/git\_agent.py                    |       47 |       33 |     30% |59-119, 126 |
| src/hsb/agents/global\_orchestrator.py          |      112 |       58 |     48% |73-81, 145-182, 228-264, 275-287, 313, 329-341 |
| src/hsb/agents/hooks.py                         |       61 |        0 |    100% |           |
| src/hsb/agents/intelligence\_agent.py           |        6 |        2 |     67% |    24, 40 |
| src/hsb/agents/linear\_agent.py                 |       74 |       24 |     68% |82-125, 232, 238-245 |
| src/hsb/agents/main\_orchestrator.py            |      131 |       65 |     50% |47-49, 68-69, 72-73, 105, 167, 187-204, 215-228, 244-289, 307-384, 406-407 |
| src/hsb/agents/qa\_agent.py                     |       56 |       40 |     29% |61-120, 134-161, 176-178 |
| src/hsb/agents/risk\_agent.py                   |       77 |        4 |     95% |153, 212, 225-226 |
| src/hsb/agents/uat\_agent.py                    |       51 |       36 |     29% |49, 69-151 |
| src/hsb/agents/work\_item\_orchestrator.py      |      109 |       76 |     30% |127-131, 148-165, 175-186, 196-208, 230-375 |
| src/hsb/cli/\_\_init\_\_.py                     |        0 |        0 |    100% |           |
| src/hsb/cli/backlog.py                          |       12 |        3 |     75% |     35-44 |
| src/hsb/cli/builder.py                          |       18 |        7 |     61% |     41-62 |
| src/hsb/cli/git.py                              |       20 |        7 |     65% |31-38, 55-61 |
| src/hsb/cli/main.py                             |      117 |       15 |     87% |167-171, 179, 203-211, 244, 246, 248, 252, 268, 317-320, 336 |
| src/hsb/cli/qa.py                               |       22 |       10 |     55% |     44-73 |
| src/hsb/contracts/\_\_init\_\_.py               |        0 |        0 |    100% |           |
| src/hsb/contracts/backlog.py                    |       37 |        0 |    100% |           |
| src/hsb/contracts/base.py                       |       22 |        0 |    100% |           |
| src/hsb/contracts/builder.py                    |       40 |        0 |    100% |           |
| src/hsb/contracts/git.py                        |       25 |        0 |    100% |           |
| src/hsb/contracts/global\_orchestrator.py       |       16 |        0 |    100% |           |
| src/hsb/contracts/knowledge.py                  |       30 |        0 |    100% |           |
| src/hsb/contracts/linear.py                     |       31 |        0 |    100% |           |
| src/hsb/contracts/main\_orchestrator.py         |       20 |        0 |    100% |           |
| src/hsb/contracts/orchestrator.py               |       15 |        0 |    100% |           |
| src/hsb/contracts/qa.py                         |       58 |        0 |    100% |           |
| src/hsb/contracts/risk.py                       |       23 |        0 |    100% |           |
| src/hsb/contracts/uat.py                        |       22 |        0 |    100% |           |
| src/hsb/runtime/\_\_init\_\_.py                 |        3 |        0 |    100% |           |
| src/hsb/runtime/claude.py                       |        5 |        0 |    100% |           |
| src/hsb/runtime/codex.py                        |       24 |        0 |    100% |           |
| src/hsb/runtime/codex\_guards.py                |       21 |        1 |     95% |        65 |
| src/hsb/runtime/compat.py                       |       75 |        0 |    100% |           |
| src/hsb/runtime/handle.py                       |       20 |        0 |    100% |           |
| src/hsb/runtime/policy.py                       |        8 |        0 |    100% |           |
| src/hsb/runtime/protocol.py                     |       23 |        0 |    100% |           |
| src/hsb/runtime/resolver.py                     |       34 |        1 |     97% |        60 |
| src/libs/\_\_init\_\_.py                        |        0 |        0 |    100% |           |
| src/libs/linear/\_\_init\_\_.py                 |        4 |        0 |    100% |           |
| src/libs/linear/linear\_client.py               |      284 |        0 |    100% |           |
| src/libs/linear/schemas.py                      |      180 |        0 |    100% |           |
| src/libs/logging.py                             |       31 |        0 |    100% |           |
| src/llm\_providers/\_\_init\_\_.py              |       10 |        0 |    100% |           |
| src/llm\_providers/auth/\_\_init\_\_.py         |        4 |        0 |    100% |           |
| src/llm\_providers/auth/api\_key.py             |       13 |        0 |    100% |           |
| src/llm\_providers/auth/base.py                 |       10 |        0 |    100% |           |
| src/llm\_providers/auth/factory.py              |       48 |        0 |    100% |           |
| src/llm\_providers/auth/oauth2\_cli.py          |       13 |        0 |    100% |           |
| src/llm\_providers/base.py                      |       33 |        0 |    100% |           |
| src/llm\_providers/errors.py                    |       44 |        0 |    100% |           |
| src/llm\_providers/prompt.py                    |       15 |        0 |    100% |           |
| src/llm\_providers/protocol.py                  |       30 |        0 |    100% |           |
| src/llm\_providers/providers/\_\_init\_\_.py    |        1 |        0 |    100% |           |
| src/llm\_providers/providers/\_codex\_config.py |       26 |        0 |    100% |           |
| src/llm\_providers/providers/claude.py          |      144 |        0 |    100% |           |
| src/llm\_providers/providers/openai.py          |      132 |        0 |    100% |           |
| src/llm\_providers/registry.py                  |       68 |        0 |    100% |           |
| src/llm\_providers/tools.py                     |       22 |        0 |    100% |           |
| src/settings/\_\_init\_\_.py                    |       39 |        0 |    100% |           |
| src/settings/codex.py                           |        6 |        0 |    100% |           |
| src/settings/credentials.py                     |        6 |        0 |    100% |           |
| src/settings/github.py                          |        5 |        0 |    100% |           |
| src/settings/linear.py                          |        7 |        0 |    100% |           |
| src/settings/logging.py                         |        6 |        0 |    100% |           |
| src/settings/orchestrator.py                    |        6 |        0 |    100% |           |
| src/settings/provider.py                        |       80 |        0 |    100% |           |
| src/settings/runtime.py                         |       49 |        0 |    100% |           |
| src/settings/test\_fixture.py                   |        9 |        0 |    100% |           |
| src/settings/wio\_ipc.py                        |        6 |        0 |    100% |           |
| src/tools/\_\_init\_\_.py                       |        3 |        0 |    100% |           |
| src/tools/linear.py                             |      106 |        0 |    100% |           |
| src/utils/\_\_init\_\_.py                       |        0 |        0 |    100% |           |
| src/utils/json.py                               |       26 |        4 |     85% |20-21, 24, 37 |
| src/utils/prompt.py                             |       10 |        0 |    100% |           |
| **TOTAL**                                       | **3470** |  **439** | **87%** |           |


## Setup coverage badge

Below are examples of the badges you can use in your main branch `README` file.

### Direct image

[![Coverage badge](https://raw.githubusercontent.com/hugo-hsbtech/task-management-agents/python-coverage-comment-action-data/badge.svg)](https://htmlpreview.github.io/?https://github.com/hugo-hsbtech/task-management-agents/blob/python-coverage-comment-action-data/htmlcov/index.html)

This is the one to use if your repository is private or if you don't want to customize anything.

### [Shields.io](https://shields.io) Json Endpoint

[![Coverage badge](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/hugo-hsbtech/task-management-agents/python-coverage-comment-action-data/endpoint.json)](https://htmlpreview.github.io/?https://github.com/hugo-hsbtech/task-management-agents/blob/python-coverage-comment-action-data/htmlcov/index.html)

Using this one will allow you to [customize](https://shields.io/endpoint) the look of your badge.
It won't work with private repositories. It won't be refreshed more than once per five minutes.

### [Shields.io](https://shields.io) Dynamic Badge

[![Coverage badge](https://img.shields.io/badge/dynamic/json?color=brightgreen&label=coverage&query=%24.message&url=https%3A%2F%2Fraw.githubusercontent.com%2Fhugo-hsbtech%2Ftask-management-agents%2Fpython-coverage-comment-action-data%2Fendpoint.json)](https://htmlpreview.github.io/?https://github.com/hugo-hsbtech/task-management-agents/blob/python-coverage-comment-action-data/htmlcov/index.html)

This one will always be the same color. It won't work for private repos. I'm not even sure why we included it.

## What is that?

This branch is part of the
[python-coverage-comment-action](https://github.com/marketplace/actions/python-coverage-comment)
GitHub Action. All the files in this branch are automatically generated and may be
overwritten at any moment.