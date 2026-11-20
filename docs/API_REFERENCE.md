# Referência da API (`pylogiccircuit`)

Todos os símbolos públicos podem ser importados diretamente do pacote raiz:

```python
from pylogiccircuit import (
    Project,
    Circuit,
    Gate,
    GateSpec,
    Simulator,
    TruthTableResult,
    VerificationResult,
    RoutingError,
    render_circuit_png,
    verify_connectivity,
    build_wire_graph,
    auto_route_nets,
    compute_subcircuit_layout,
    parse_gate_guid,
)
```

---

## 1. `Project` (`pylogiccircuit.project`)

Representa um arquivo completo `.CircuitProject` do LogicCircuit.

### Construtor

```python
Project(
    name: str = "Project",
    project_id: Optional[str] = None,
    zoom: float = 1.0,
    frequency: int = 10,
)
```

### Métodos

| Método | Assinatura / Retorno | Descrição |
| --- | --- | --- |
| `add_circuit` | `(name, notation="", circuit_shape=None, circuit_id=None, set_main=False) -> Circuit` | Cria e registra um novo circuito no projeto. O primeiro circuito (ou `set_main=True`) vira o circuito principal ao abrir no LogicCircuit. |
| `get_circuit` | `(name_or_id: str) -> Circuit` | Busca um circuito pelo `name` ou pelo GUID (`circuit_id`). Lança `KeyError` se não existir. |
| `to_xml_tree` | `() -> ET.ElementTree` | Gera a árvore XML em conformidade estrita com a ordem do XSD `2.0.0.14`. |
| `save` | `(path: str \| Path) -> Path` | Salva o arquivo `.CircuitProject` em UTF-8 (cria diretórios pai automaticamente). |
| `Project.load` | `classmethod (path: str \| Path) -> Project` | Carrega um `.CircuitProject` existente, preservando elementos extras (`CircuitButton`, `TextNote`, etc.). |

---

## 2. `Circuit` (`pylogiccircuit.project`)

Representa uma folha lógica (`LogicalCircuit`) contendo pinos, portas, subcircuitos e fios.

### Adição de Componentes

- **`add_input(name, x, y, side="Left", inverted=False, pin_id=None, symbol_id=None) -> PinHandle`**
  Adiciona um pino de entrada externo na posição `(x, y)` (tamanho `2×2`, ponto de conexão em `(x+2, y+1)`).
  - `side`: lado onde o pino aparece quando este circuito é usado como subcircuito (`"Left"`, `"Right"`, `"Top"`, `"Bottom"`).
  - `inverted`: se `True`, ativa a inversão lógica do pino no LogicCircuit (`Inverted="True"`).

- **`add_output(name, x, y, side="Right", inverted=False, pin_id=None, symbol_id=None) -> PinHandle`**
  Adiciona um pino de saída externo em `(x, y)` (ponto de conexão em `(x, y+1)`).

- **`add_gate(gate: GateSpec, x, y, label="", symbol_id=None) -> GateHandle`**
  Posiciona uma porta lógica nativa do LogicCircuit.
  - Retorna um `GateHandle` com `handle.in_[i]` (ou `handle.inputs[i]`) para cada entrada e `handle.out` para a saída.

- **`add_clock(x, y, label="CLK") -> PinHandle`**
  Posiciona um componente nativo de `Clock` em `(x, y)` e retorna o `PinHandle` da sua saída.

- **`add_subcircuit(subcircuit: Circuit, x, y, label="", symbol_id=None) -> SubcircuitHandle`**
  Instancia outro `Circuit` do projeto em `(x, y)`.
  - Os pinos são acessados por nome via indexação: `sub["A"]`, `sub["Cout"]`, etc.
  - Dimensões `sub.width` e `sub.height` são calculadas automaticamente pela regra do LogicCircuit.

### Conexões, Roteamento e Verificação

- **`connect(*pins: PinHandle | tuple[int, int], name: Optional[str] = None) -> None`**
  Declara uma rede elétrica ligando 2 ou mais pinos. É roteada quando `auto_route()` é chamado.

- **`add_wire(x1, y1, x2, y2) -> None`**
  Adiciona manualmente um segmento de fio reto entre `(x1, y1)` e `(x2, y2)`.

- **`auto_route(max_x=None, max_y=None, max_attempts=25, bend_cost=5.0, cross_cost=3.0, clear_existing=True) -> List[WireSegment]`**
  Roteia automaticamente todas as redes declaradas via `connect()`, valida 0 curtos com `verify_connectivity()` e popula `circuit.wires`.
  - Lança `RoutingError` se o espaço for insuficiente ou algum pino não puder ser alcançado após `max_attempts`.

- **`verify(allow_diagonal: bool = False) -> VerificationResult`**
  Audita os fios atuais do circuito: retorna `VerificationResult(ok, errors, net_components)`.

- **`symbol_layout() -> Tuple[int, int, Dict[str, Tuple[int, int]]]`**
  Retorna `(largura, altura, {nome_pino: (dx, dy)})` para quando o circuito é usado como subcircuito.

---

## 3. `Gate` e `GateSpec` (`pylogiccircuit.gates`)

Catálogo pronto de portas nativas do LogicCircuit:

| Categoria | Constantes disponíveis | Fábricas dinâmicas (`n` entradas) |
| --- | --- | --- |
| Inversor | `Gate.NOT` | — |
| AND / NAND | `Gate.AND2` .. `Gate.AND8`, `Gate.NAND2` .. `Gate.NAND4` | `Gate.and_(n)`, `Gate.nand(n)` |
| OR / NOR | `Gate.OR2` .. `Gate.OR8`, `Gate.NOR2` .. `Gate.NOR4` | `Gate.or_(n)`, `Gate.nor(n)` |
| XOR / XNOR | `Gate.XOR2` .. `Gate.XOR4`, `Gate.XNOR2` .. `Gate.XNOR4` | `Gate.xor(n)`, `Gate.xnor(n)` |
| Especiais | `Gate.CLOCK`, `Gate.LED` | — |

### Funções auxiliares de `gates.py`
- **`parse_gate_guid(guid: str) -> Optional[GateSpec]`**: decodifica qualquer GUID de porta nativa encontrado em arquivos `.CircuitProject`.
- **`compute_subcircuit_layout(pins) -> Tuple[int, int, Dict[str, Tuple[int, int]]]`**: calcula a geometria exata de um bloco de subcircuito.

---

## 4. `Simulator` e `TruthTableResult` (`pylogiccircuit.simulator`)

Simulador lógico com fila FIFO compatível com o motor do LogicCircuit.

### Criação

```python
sim = Simulator.from_project(project)
# ou diretamente de um arquivo .CircuitProject:
sim = Simulator.from_file("meu_circuito.CircuitProject")
```

### Métodos de `Simulator`

- **`evaluate(circuit_name: str, inputs: Dict[str, int], max_steps: int = 2000) -> Dict[str, int]`**
  Avalia um circuito combinacional para um vetor de entradas e devolve `{nome_saida: 0 | 1}`.
  - Lança `RuntimeError` caso o circuito oscile (exceda `max_steps`).

- **`truth_table(circuit_name: str, max_rows: Optional[int] = None, max_steps: int = 2000) -> TruthTableResult`**
  Executa a varredura sequencial completa (`0 .. 2^N - 1`) igual à janela *Truth Table* do LogicCircuit (mantendo estado interno entre linhas para latches/flip-flops e alternando `Clock` internos).

### Atributos e Métodos de `TruthTableResult`

| Campo / Método | Tipo | Descrição |
| --- | --- | --- |
| `circuit_name` | `str` | Nome do circuito avaliado |
| `input_names` | `List[str]` | Nomes das colunas de entrada na ordem `PinComparer` |
| `output_names` | `List[str]` | Nomes das colunas de saída |
| `rows` | `List[Tuple[List[int], List[int]]]` | Lista de pares `(vetor_entrada, vetor_saida)` |
| `oscillated` | `bool` | `True` se houve oscilação durante a inicialização ou alguma linha |
| `oscillation_row` | `Optional[int]` | Índice da linha onde oscilou (`-1` se oscilou na inicialização) |
| `has_internal_clocks` | `bool` | `True` se o circuito (ou subcircuitos) contém blocos `Clock` internos |
| `format_markdown()` | `str` | Formata a tabela-verdade em Markdown pronto para colar no GitHub |

---

## 5. `render_circuit_png` (`pylogiccircuit.preview`)

Renderiza qualquer `Circuit` em imagem PNG (requer `Pillow`):

```python
render_circuit_png(
    circuit: Circuit,
    output_path: str | Path,
    scale: int = 16,
    padding: int = 3,
    *,
    title: Optional[str] = None,
    show_header: bool = True,
    show_legend: bool = True,
) -> Path
```

- `scale`: pixels por unidade da grade do LogicCircuit (ex.: `20` para circuitos pequenos, `14` para ALUs grandes).
- `padding`: margem em unidades de grade ao redor do circuito.
- `title`: título personalizado na barra superior (padrão: `"{name} ({notation})"`).
- `show_header` / `show_legend`: liga/desliga a barra de título com estatísticas e a legenda inferior.

---

## 6. Funções de Baixo Nível (`verifier.py` e `router.py`)

- **`build_wire_graph(wires, pins) -> Dict[Point, int]`**: retorna o mapa `ponto -> id_componente_conexo` usando a semântica exata do LogicCircuit.
- **`verify_connectivity(wires, all_pins, expected_nets=None, allow_diagonal=False) -> VerificationResult`**: verifica curtos, redes divididas, pinos não atribuídos tocados e fios diagonais.
- **`auto_route_nets(obstacles, all_pins, nets, max_x=None, max_y=None, max_attempts=25, bend_cost=5.0, cross_cost=3.0) -> List[WireSegment]`**: interface direta para o roteador ortogonal A\*.

---

## 7. Receita Prática: Carregar, Auditar e Modificar um Projeto Existente

```python
from pylogiccircuit import Project, Simulator, render_circuit_png

proj = Project.load("meu_trabalho.CircuitProject")

# Listar todos os circuitos e verificar geometria
for c in proj.circuits:
    res = c.verify(allow_diagonal=True)
    print(f"{c.name}: ok={res.ok}, symbols={len(c.symbols)}, wires={len(c.wires)}")

# Simular a tabela-verdade de um circuito específico
sim = Simulator.from_project(proj)
tt = sim.truth_table("somador")
print(tt.format_markdown())

# Gerar prévia PNG de alta resolução
render_circuit_png(proj.get_circuit("somador"), "somador_preview.png", scale=18)
```
