# Config README

鏈枃妗ｄ笌褰撳墠浠ｇ爜瀹炵幇鍚屾锛岃鏄?`config.yaml` 涓摢浜涘瓧娈典細瀹為檯褰卞搷缈昏瘧锛屽摢浜涘瓧娈典粎涓哄吋瀹逛繚鐣欍€?
## 1. 鍔犺浇瑙勫垯

- 鏀寔 `YAML` / `JSON`銆?- 浠呰鐩栦綘鏄惧紡濉啓鐨勫瓧娈碉紝鏈～鍐欎娇鐢ㄩ粯璁ゅ€笺€?- 鏈瘑鍒瓧娈典細琚拷鐣ワ紙涓嶄細鎶ラ敊锛夈€?- 寮€鍚?`--resume` 鏃讹紝宸插懡涓殑缂撳瓨娈佃惤涓嶄細閲嶇炕锛涢厤缃敼鍔ㄦ兂鍏ㄩ潰鐢熸晥璇峰叧闂?`resume` 鎴栨洿鎹?`cache.sqlite`銆?
## 2. 榛樿閰嶇疆锛堝缓璁級

褰撳墠椤圭洰榛樿妯℃澘鏈€灏忓寲涓猴細

```yaml
style: faithful_literal
translate_toc: true
translate_titles: true
```

鍏朵綑椤逛娇鐢ㄥ唴缃粯璁ゅ€硷紙瑙佷笅鏂?4.2锛夈€?
## 3. UI 涓彲缂栬緫涓斿疄闄呯敓鏁堢殑瀛楁


- 目标语言固定为简体中文（zh-Hans），不再通过 config 配置。

- `style`
  - 浣滅敤锛氱炕璇?娑﹁壊椋庢牸锛屼細鐩存帴杩涘叆 LLM payload 鐨?`style_guide`
  - 鍙€夋灇涓撅細
    - `faithful_literal`锛氬繝瀹炵洿璇戯紙榛樿锛屾妧鏈枃妗?鏈鏁忔劅锛?    - `faithful_fluent`锛氬繝瀹炰絾鏇撮『鐣咃紙閫氱敤闃呰锛?    - `literary_cn`锛氬亸涔﹂潰鏂囬锛堝皬璇?鏁ｆ枃锛?    - `concise_cn`锛氭洿绠€娲佸嚌缁冿紙鎽樿/閫熻锛?  - 闈炴硶鍊间細鑷姩鍥為€€鍒?`faithful_literal`

### 3.2 鍐呭鑼冨洿

- `translate_toc`锛氭槸鍚︾炕璇戠洰褰曟枃鏈?- `translate_titles`锛氭槸鍚︾炕璇?HTML `title` 鑺傜偣

### 3.3 鍒嗘

- `segmentation.max_chars_per_segment`锛氬崟娈垫渶澶у瓧绗︽暟
- `segmentation.max_chars_per_batch`锛氬崟鎵瑰瓧绗︿笂闄?- `segmentation.max_segments_per_batch`锛氬崟鎵规鏁颁笂闄?
### 3.4 涓婁笅鏂?
- `context.prev_segment_chars`锛氬墠鏂囨埅鏂暱搴?
### 3.5 LLM 璋冪敤

- `llm.temperature`
- `llm.max_retries`
- `llm.retry_backoff_seconds`
- `llm.timeout_seconds`

### 3.6 QA 闂ㄦ

- `qa.warn_ratio_limit`
- `qa.warn_min_cap`

楠屾敹瑙勫垯锛?
`warn_cap = max(int(total_segments * warn_ratio_limit), warn_min_cap)`  
浠呭綋 `error_count == 0` 涓?`warn_count <= warn_cap` 鎵嶉€氳繃 gate銆?
## 4. 鍏煎瀛楁璇存槑

### 4.1 宸插垹闄ゅ瓧娈碉紙鏃ч厤缃噷浼氳蹇界暐锛?
- `quote_mode.*`
- `poetry_mode`
- `code_mode`

### 4.2 鐩墠淇濈暀鍦ㄩ厤缃ā鍨嬩腑锛屼絾 UI 宸查殣钘忥紙褰撳墠鐗堟湰涓嶉┍鍔ㄤ富娴佺▼锛?
杩欎簺瀛楁浠嶆湁榛樿鍊煎苟鍙啓鍏ラ厤缃紝浣嗗綋鍓嶉€昏緫涓嶆寜瀹冧滑鍒嗘敮锛?
- `latin_mode.translate_normally`
- `table_mode.preserve_numbers`
- `table_mode.preserve_abbreviations`
- `segmentation.sentence_split_fallback`
- `context.use_prev_segment`
- `context.use_term_hints`

## 5. 甯哥敤璋冨弬妯℃澘

### 5.1 绋冲畾浼樺厛

```yaml
segmentation:
  max_chars_per_segment: 800
  max_chars_per_batch: 8000
  max_segments_per_batch: 25

llm:
  max_retries: 6
  timeout_seconds: 180
```

### 5.2 閫熷害浼樺厛锛堢綉缁滅ǔ瀹氭椂锛?
```yaml
segmentation:
  max_chars_per_batch: 15000
  max_segments_per_batch: 60
```

骞堕厤鍚堟彁楂?`max_concurrency`锛堣 provider 闄愭祦鑰屽畾锛夈€?
## 6. 甯歌闂

- 鏀逛簡閰嶇疆浣嗙粨鏋滄病鍙樺寲锛?  - 鍏堟鏌ユ槸鍚﹀紑鍚簡 `resume` 鍛戒腑缂撳瓨銆?- 鍙互鍐欓澶栧瓧娈靛悧锛?  - 鍙互鍐欙紝浣嗘湭璇嗗埆瀛楁浼氳蹇界暐銆?
