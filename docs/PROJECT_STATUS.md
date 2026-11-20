# Estado Atual do Projeto (`v0.1.0`)

Este documento registra o **estado atual completo** da biblioteca **`pylogiccircuit`**, cobrindo tudo o que já está implementado e validado, a matriz de compatibilidade com o [LogicCircuit](https://www.logiccircuit.org/), limitações conhecidas e o roadmap das próximas entregas.

---

## 1. Resumo Executivo

A `pylogiccircuit` já é uma biblioteca Python funcional, empacotada via `pyproject.toml`, **sem dependências obrigatórias no núcleo** (100% biblioteca padrão do Python 3.10+), capaz de:

1. **Construir circuitos digitais via código Python** (portas lógicas primitivas, pinos de entrada/saída, clocks, LEDs e subcircuitos hierárquicos aninhados).
2. **Rotear fios automaticamente** na grade do LogicCircuit usando busca A\* ortogonal com proteção de saída de pinos e *rip-up-and-reroute*, garantindo zero curtos.
3. **Verificar conectividade e geometria exata** segundo as regras reais do LogicCircuit (cruzamentos perpendiculares não conectam; pontas/junções em T conectam; segmentos colineares sobrepostos conectam).
4. **Simular circuitos combinacionais e sequenciais** com fila FIFO (*DirtyList*) compatível com o motor do LogicCircuit, gerando tabelas-verdade completas e detectando oscilações.
5. **Ler e salvar arquivos `.CircuitProject`** respeitando a ordem exata do esquema XSD `http://LogicCircuit.net/2.0.0.14/CircuitProject.xsd`.
6. **Renderizar prévias visuais em PNG** (dependência opcional `Pillow`) com grade, bolhas de inversão, pontos de junção em T, cabeçalho de estatísticas e legenda.
7. **Operar via linha de comando (CLI)** com `pylogiccircuit list | verify | truth-table | render`.

---

## 2. Inventário de Módulos (Estado Atual)

| Módulo | Linhas | Responsabilidade | Dependências | Status |
| --- | --: | --- | --- | :---: |
| [`src/pylogiccircuit/__init__.py`](../src/pylogiccircuit/__init__.py) | 46 | Exports públicos e versão (`0.1.0`) | Stdlib | Pronto |
| [`src/pylogiccircuit/gates.py`](../src/pylogiccircuit/gates.py) | 245 | Catálogo de GUIDs nativos do LogicCircuit, avaliação booleana e geometria de pinos/subcircuitos | Stdlib | Pronto |
| [`src/pylogiccircuit/project.py`](../src/pylogiccircuit/project.py) | 626 | API fluente (`Project`, `Circuit`, handles) e serialização/desserialização XML `.CircuitProject` | Stdlib | Pronto |
| [`src/pylogiccircuit/router.py`](../src/pylogiccircuit/router.py) | 383 | Roteador ortogonal A\* com stubs, *escape guards*, *pin halo* e *rip-up-and-reroute* | Stdlib | Pronto |
| [`src/pylogiccircuit/verifier.py`](../src/pylogiccircuit/verifier.py) | 154 | Grafo exato de conectividade e validação de curtos, redes desconexas e fios diagonais | Stdlib | Pronto |
| [`src/pylogiccircuit/simulator.py`](../src/pylogiccircuit/simulator.py) | 385 | Achatamento hierárquico (Union-Find), motor FIFO, tabela-verdade e detecção de oscilação | Stdlib | Pronto |
| [`src/pylogiccircuit/preview.py`](../src/pylogiccircuit/preview.py) | 292 | Renderização de esquemáticos em PNG (cabeçalho, legenda, bolhas de inversão, pontos de junção) | Pillow *(opcional)* | Pronto |
| [`src/pylogiccircuit/cli.py`](../src/pylogiccircuit/cli.py) | 84 | Interface de terminal (`list`, `verify`, `truth-table`, `render`) | Stdlib (+ Pillow p/ `render`) | Pronto |

**Total do pacote principal (`src/pylogiccircuit/`):** `2.215` linhas de Python tipado.

---

## 3. Validação e Qualidade

### Suíte de Testes (`pytest`)

| Arquivo de Teste | Cobertura Principal | Status |
| --- | --- | :---: |
| [`tests/test_gates_and_xml.py`](../tests/test_gates_and_xml.py) | Decodificação de GUIDs, tabelas de portas, geometria 4 lados de subcircuitos, round-trip XML e ordem XSD | Passando |
| [`tests/test_router_and_verifier.py`](../tests/test_router_and_verifier.py) | Cruzamento perpendicular sem curto, detecção de curto em junção T, fios diagonais, roteamento cruzado | Passando |
| [`tests/test_simulator.py`](../tests/test_simulator.py) | Half Adder, somador 2-bit hierárquico, Ring Oscillator (detecção de oscilação), SR Latch NAND | Passando |
| [`tests/test_preview_and_cli.py`](../tests/test_preview_and_cli.py) | Renderização PNG (opções de cabeçalho/legenda/título) e subcomandos CLI (`list`, `verify`, `truth-table`, `render`) | Passando |

### Exemplos Executáveis Verificados

| Exemplo | Circuito | Verificação Exaustiva | Prévia Gerada |
| --- | --- | --- | --- |
| [`examples/half_adder.py`](../examples/half_adder.py) | Half Adder 1-bit | `4 / 4` linhas da tabela-verdade | [`docs/images/half_adder.png`](images/half_adder.png) |
| [`examples/full_adder_4bit.py`](../examples/full_adder_4bit.py) | Full Adder 1-bit + Somador 4-bit hierárquico | `512 / 512` combinações | [`docs/images/full_adder_1bit.png`](images/full_adder_1bit.png), [`docs/images/adder_4bit.png`](images/adder_4bit.png) |
| [`examples/alu_4bit_74ls382.py`](../examples/alu_4bit_74ls382.py) | Seletor `BitMux` + ALU 4-bit `74LS382/74HC382` | `4096 / 4096` combinações (`F3..F0`, `Cn+4`, `OVR`) | [`docs/images/bit_mux.png`](images/bit_mux.png), [`docs/images/alu_74ls382.png`](images/alu_74ls382.png) |

### Integração Contínua (CI)
- Workflow configurado em [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) executando `pytest -v` e os 3 exemplos em matriz Python `3.10`, `3.11`, `3.12` e `3.13` a cada `push` e `pull_request` na branch `main`.

---

## 4. Matriz de Compatibilidade com o LogicCircuit (`2.0.0.14`)

| Recurso do LogicCircuit | Construção via API | Leitura / Escrita XML | Auto-Router | Simulador FIFO | Preview PNG |
| --- | :---: | :---: | :---: | :---: | :---: |
| Pinos `Input` / `Output` (1 bit, 4 lados, inversão) | Sim | Sim | Sim | Sim | Sim |
| Portas `NOT`, `AND`, `NAND`, `OR`, `NOR`, `XOR`, `XNOR` (1..8 entradas) | Sim | Sim | Sim | Sim | Sim |
| Subcircuitos hierárquicos (qualquer profundidade) | Sim | Sim | Sim | Sim | Sim |
| `Clock` interno | Sim | Sim | Sim | Sim *(alterna por linha)* | Sim |
| `LED` (1 bit) | Sim | Sim | Sim | Ignorado (observador) | Sim |
| `CircuitButton`, `TextNote`, `Constant`, `Sensor`, `Memory`, `CircuitProbe` | — | Preservados no `load`/`save` | — | Não simulado ainda | Genérico |
| Barramentos multi-bit (`BitWidth > 1`) e `Splitter` | Não ainda | Preservados via atributos extras | Não ainda | 1 bit atualmente | Não ainda |

---

## 5. Limitações Conhecidas Atuais

1. **Posicionamento manual de blocos (`x`, `y`)**: atualmente o usuário informa as coordenadas `(x, y)` de cada pino, porta e subcircuito, e a biblioteca faz o roteamento automático dos fios (`auto_route()`). Ainda não existe um *auto-placer* topológico automático.
2. **Largura de barramento fixa em 1 bit no simulador**: pinos e portas com `BitWidth > 1` e componentes `Splitter` ainda não são simulados nativamente (embora possam existir no XML).
3. **Componentes avançados do LogicCircuit**: `Constant`, `Memory` (ROM/RAM), `Sensor`, `Button` e `LedMatrix` ainda não possuem builders dedicados nem modelos de simulação.
4. **Orientação/Rotação de símbolos**: o roteador assume a orientação padrão esquerda→direita das portas (como usado por padrão no LogicCircuit).

---

## 6. Roadmap

### `v0.2.0` — Componentes e Conveniência
- [ ] Builders dedicados para `Constant` (0/1), `Button`, `Probe` e `TextNote`.
- [ ] Suporte a barramentos multi-bit (`BitWidth`) e `Splitter` na API e no simulador.
- [ ] Simulação passo a passo com controle explícito de bordas de clock (`sim.step()`, `sim.tick()`).

### `v0.3.0` — Layout Automático e Exportação
- [ ] *Auto-placer* em camadas topológicas (permitindo omitir `x, y` e gerar um layout legível automaticamente).
- [ ] Exportação de esquemáticos em **SVG** vetorial (além de PNG).
- [ ] Helpers prontos de blocos clássicos (`pylogiccircuit.stdlib`: Mux, Decoder, FullAdder, RippleAdder, FlipFlops).

### `v1.0.0` — Publicação no PyPI
- [ ] Publicação oficial no PyPI (`pip install pylogiccircuit`).
- [ ] Suporte completo a simulação de `ROM`/`RAM` e documentação online (MkDocs / GitHub Pages).
