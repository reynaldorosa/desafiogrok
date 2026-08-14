# Nash loop — iterações de crítica

Três jogadores, uma pergunta: *como colorir exatamente G(n=30, p=0.35)
em Python puro, χ ótimo, média < 5 s?*

Ferramenta: `mcp-reasoner / nash_loop` (DeepSeek + GLM, `max_refinements=3`,
`show_steps=true`). Grok é o terceiro jogador: propõe, lê as duas críticas,
rejeita o que é insound e implementa o equilíbrio.

| Jogador | Papel | Job | Resultado do juiz |
|---|---|---|---|
| Grok 4.6 | proposta inicial + síntese final + código | — | implementou |
| GLM 5.2 | `nash_loop` provider=`glm` | `97c39544-ed1c-400d-b313-2da37023bf87` | score **1.00** (autoavaliação — juiz sem independência) |
| DeepSeek V4 | `nash_loop` provider=`deepseek` | `d7681024-66e1-4712-9cc0-c7df659daaae` | score não-parseável; candidata entregue |
| ensemble_judge | nota estável da síntese | — | **0.97** (σ = 0.03, 2/3 julgamentos) |

---

## Iteração 0 — Grok (proposta)

Família **DSATUR B&B em bitsets**:

1. LB = clique máxima exata (Bron–Kerbosch + pivô de Tomita).
2. UB = DSATUR greedy + Culberson iterated greedy + first-fit aleatório.
3. Decisão: `k`-colorabilidade para `k = LB, LB+1, …, UB-1`.
4. Pré-colorir a clique com `0..ω-1`.
5. Simetria: nunca introduzir a cor `c` se `c-1` ainda não foi usada
   (coloração canônica / prefixo).
6. Forward checking + unit propagation + desfazer por deltas.
7. Sem SAT/MIP, sem numpy.

Riscos que o Grok pediu para atacar: explosão no rabo χ=ω+2;
gap largo do IG; segundo LB; simetria que poda a única coloração ótima;
DSATUR sem tie-break de grau; DPLL artesanal mais lento.

---

## Iteração 1 — GLM (nash_loop)

**Algoritmo nomeado:** *Tomita LB → DSATUR+IG UB → DSATUR k-B&B
com FC, unit-prop, simetria prefixo, e “greedy re-LB” no residual.*

Concordou com a família. Mudanças úteis que **entramos**:

- unit propagation iterativa antes de cada branch;
- simetria escrita como `break` quando `c > n_colors_used`
  (prefixo, começando em ω por causa da clique);
- **sem timeout** — um fuse que “sobe para k+1” devolveria χ subótimo;
- k-loop ascendente em vez de B&B direto em χ;
- early-exit do stack de UB quando `UB == LB`.

### Crítica do Grok à GLM (bloqueio de soundness)

GLM propôs, em todo nó com ≥ 12 vértices por colorir:

> rode um greedy no residual; se `n_colors_used + greedy > k`, pode.

Isso é **inválido**. Greedy no residual é um **teto** de χ, não um piso.
Um residual 3-colorível que o greedy pinta com 5 cores seria podado
num teste de 4-colorabilidade — e o solver devolveria χ demais.

**Decisão:** greedy no residual só **aceita** (se completar com ≤ k cores).
Nunca poda.

O 1.00 da GLM é auto-nota (mesmo modelo gerou e julgou). Não usamos
esse número como evidência.

---

## Iteração 2 — DeepSeek (nash_loop)

**Algoritmo nomeado:** *LTDS — Lawler–Tomita Decision Search.*

Troca a fase exata por ramificação em **classes de cor**:

> G é k-colorível ⇔ existe um conjunto independente maximal S ∋ v
> tal que G−S é (k−1)-colorível.

Memo `(mask, k)`, split por componentes, atalho bipartido, atalho
greedy (aceite). Isso é uma família clássica e **soa** — *exceto* o LB.

### Crítica do Grok à DeepSeek (bloqueio de soundness)

DeepSeek escreveu:

> q = cores do greedy ⇒ q é teto de α(mask) ⇒ χ ≥ ceil(\|V\| / q).
> Se ceil(\|V\| / q) > k, falhe.

Falso. q é teto de **χ**, não de α. α ≥ ceil(n/q), o que só reproduz
χ ≤ q. Contra-exemplo: um bipartido que o greedy pinte com 3 cores
teria `ceil(30/3)=10 > 3` e seria declarado não-3-colorível.

Moon–Moser (3^{n/3} MIS) também é o pior caso, não o típico — e
enumerar MIS de um residual de ~19 vértices em CPython pode
explodir no rabo, exatamente o regime que o desafio pune.

**Decisão:** não trocar o motor. Ficar com DSATUR B&B. Aproveitar
do DeepSeek só o que é barato e correto: aceitar residual independente;
`|U| ≤ k` sem restrições de saturação não foi usado (as máscaras
ainda podem esvaziar o domínio).

---

## Iteração 3 — equilíbrio (Grok)

| Peça | Origem | Entrou? |
|---|---|---|
| Bitsets + DSATUR B&B + k-loop | Grok | sim |
| Clique Tomita / Bron–Kerbosch | Grok + ambos | sim |
| α exato via clique do complemento; LB = max(ω, ceil(n/α)) | Grok | sim |
| Iterated greedy + DSATUR UB | Grok + GLM + DeepSeek | sim |
| Prefixo fresco + pré-cor da clique | Grok, formalizado pela GLM | sim |
| Unit propagation + FC + delta-undo | GLM | sim |
| Sem timeout | GLM (e Grok, na síntese) | sim |
| k-core (deg < k por último) | Grok, na implementação | sim |
| Matching clique residual ↔ cores | Grok | sim (sound, matching exato) |
| Greedy residual como **LB** | GLM | **não** |
| ceil(n/q_greedy) como LB | DeepSeek | **não** |
| Lawler / enumeração de MIS | DeepSeek | **não** (custo + risco de cauda) |
| Greedy residual como **aceite** | DeepSeek (atalho) + Grok | sim, só se \|U\| ≤ 14 |
| Residual independente ⇒ aceite | DeepSeek / Grok | sim |

Nome do equilíbrio:

> **Bitset DSATUR k-B&B**, LB Tomita+α, UB DSATUR+IG,
> núcleo-k + clique pré-colorida, simetria prefixo,
> FC + unit-prop, matching da clique residual,
> greedy só para aceitar.

---

## Iteração 4 — medida (não previsão)

CPython 3.14.4, Xeon E5-2673 v3 @ 2.40 GHz, seeds `0..199`,
`G(30, 0.35)`, timer só em `solve()`:

| métrica | valor | alvo |
|---|---|---|
| corretas | **200 / 200** | 200 / 200 |
| média | **0.0196 s** | < 5 s |
| mediana | 0.0237 s | — |
| p95 | **0.0267 s** | < 15 s |
| máx | 0.0280 s | não pendurar |
| histograma χ | 4:1  5:92  6:106  7:1 | — |

`ensemble_judge` (DeepSeek, 2 amostras válidas): **0.97**, σ = 0.03.

Testes de grafos clássicos (Petersen χ=3, Grötzsch χ=4, ciclos ímpares/pares,
rodas, K_n, bipartidos) passam. Dois “falhados” na primeira bateria eram
expectativa errada do teste (roda par tem χ=3, não 4; o circulante C₁₂(1,4)
não é o grafo de Chvátal).

---

## Como reproduzir o loop

Os traces brutos do MCP ficam na sessão Grok; este arquivo é a ata.
Para reexecutar o juiz:

```
mcp-reasoner.nash_loop  provider=glm|deepseek
    question=<spec G(30,0.35) exact>
    max_refinements=3  show_steps=true  threshold=0.80
```

Para reexecutar o solver:

```
python3 graphcolor.py --bench 200 --n 30 --p 0.35 --verbose
```
