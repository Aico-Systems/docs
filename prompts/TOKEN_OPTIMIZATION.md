# Token Optimization

Reduce costs and latency by using appropriate models and token limits.

## Model Selection

| Use Case                             | Model         |
| ------------------------------------ | ------------- |
| Complex intent classification        | `gpt-4o`      |
| Information extraction (smart entry) | `gpt-4o`      |
| Simple yes/no questions              | `gpt-4o-mini` |
| Slot filling                         | `gpt-4o-mini` |
| Status formatting                    | `gpt-4o-mini` |
| Confirmations                        | `gpt-4o-mini` |

## maxTokens Guidelines

| Response Type      | maxTokens |
| ------------------ | --------- |
| Yes/No answer      | 80-100    |
| Short confirmation | 100-150   |
| Status explanation | 200-250   |
| Complex response   | 300-400   |
