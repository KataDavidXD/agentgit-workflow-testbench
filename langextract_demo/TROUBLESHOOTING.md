# LangExtract 演示 - 问题排查日志

## 问题总结

在配置和运行 LangExtract demo 时遇到的问题和解决方案。

---

## 问题 1: 模型名称不支持 ❌

### 错误信息
```
InferenceConfigError: No provider registered for model_id='gpt4o-mini'
Available patterns: ['^gpt-4', '^gpt-5', '^gemini', ...]
```

### 原因
LangExtract 使用基于正则表达式的模型路由器。`gpt4o-mini` 不匹配任何支持的模式。

### 解决方案
将模型名称改为支持的型号：
- ❌ `gpt4o-mini` 
- ✅ `gpt-4-turbo` (匹配 `^gpt-4` 模式)

### 修复方式
在 `config.py` 中修改默认模型：
```python
model = os.getenv("DEFAULT_LLM", "gpt-4-turbo")  # 改成 gpt-4-turbo
```

或在环境变量中设置：
```powershell
$env:DEFAULT_LLM = "gpt-4-turbo"
```

---

## 问题 2: API 端点未正确传递 ❌

### 错误特征
- 配置中有 `LLM_BASE_URL`，但似乎没有被加载
- OpenAI client 仍然使用默认端点而不是自定义端点

### 原因
在 `config.py` 中，参数被命名为 `model_url`，但 OpenAI provider 期望的参数名是 `base_url`。

```python
# ❌ 错误
config["model_url"] = base_url

# ✅ 正确
config["base_url"] = base_url
```

### 解决方案
1. 在 `config.py` 中，将参数名改为 `base_url`：
```python
if base_url:
    config["base_url"] = base_url  # 关键修复
```

2. 在 `main.py` 中，从 `provider_kwargs` 中移除 `model` 键（因为它不是 provider 参数）：
```python
provider_kwargs = {k: v for k, v in config_dict.items() if k != 'model'}

result = lx.extract(
    ...,
    config=lx.factory.ModelConfig(
        model_id=config_dict["model"],
        provider_kwargs=provider_kwargs  # 包含正确的 base_url
    )
)
```

---

## 最终成功运行 ✅

```
Using model: gpt-4-turbo
API endpoint: https://rtekkxiz.bja.sealos.run/v1

============================================================
EXTRACTION RESULTS
============================================================

#1 CHARACTER
   Text: Lady Juliet
   Position: [0:11]
   Alignment: match_exact
   Attributes: {'action': 'gazed longingly at the stars', 'emotional_state': 'heart aching for Romeo'}

#2 EMOTION
   Text: longingly
   Position: [18:27]
   Alignment: match_exact
   Attributes: {'type': 'yearning'}

#3 RELATIONSHIP
   Text: her heart aching for Romeo
   Position: [42:68]
   Alignment: match_exact
   Attributes: {'type': 'unrequited love', 'from': 'Lady Juliet', 'to': 'Romeo'}
```

---

## 关键知识点

### 1. LangExtract 的模型路由机制
- 使用正则表达式匹配模型 ID
- 支持的提供商有内置的模式列表
- 可通过显式指定 provider class 来绕过路由

### 2. OpenAI 兼容 API 配置
- 需要设置 `base_url` 参数（不是 `model_url`）
- `api_key` 仍然使用标准的 OpenAI API key
- 支持任何 OpenAI 兼容的端点（如 Sealos, LocalAI 等）

### 3. LangExtract 的提取管道
```
文本 → 分块 → 生成 Prompt → LLM 推理 → 解析输出 → 对齐到原文 → 结果
```

提取结果包含：
- `extraction_class`: 提取类别（如 "character", "emotion"）
- `extraction_text`: 提取的文本
- `char_interval`: 在原文中的字符位置
- `alignment_status`: 对齐状态（match_exact, match_fuzzy 等）
- `attributes`: 额外属性

---

## 完整工作流程

1. **配置环境变量**
   ```powershell
   $env:LLM_API_KEY = "your-api-key"
   $env:LLM_BASE_URL = "https://your-endpoint/v1"
   $env:DEFAULT_LLM = "gpt-4-turbo"
   ```

2. **运行演示**
   ```powershell
   .venv\Scripts\python.exe langextract_demo/main.py
   ```

3. **查看结果**
   - 控制台输出提取结果
   - `extraction_results.jsonl` 保存原始数据
   - `visualization.html` 生成可视化界面

---

## 总结

| 问题 | 原因 | 解决方案 |
|------|------|--------|
| 模型不支持 | 名称不匹配正则表达式 | 使用 `gpt-4-turbo` |
| 端点不加载 | 参数名错误 (`model_url` vs `base_url`) | 改用 `base_url` |
| 提取不显示 | 参数传递问题 | 过滤 provider_kwargs |

现在 LangExtract 演示已完全正常工作！

