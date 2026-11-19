# Cola BD2 - Conceitos e Sintaxe

Nov 19, 2026 · @Davi

## 1. Stored Procedure

Bloco de SQL salvo no servidor, com nome, executado com `CALL`. Serve para reaproveitar código, dar segurança (usuário executa sem acessar a tabela) e diminuir tráfego entre aplicação e banco.

| Parâmetro | Uso |
| --- | --- |
| `IN` | entra (padrão) |
| `OUT` | sai, volta numa `@variavel` |
| `INOUT` | entra e sai |

- `DECLARE` = variável local (só dentro do BEGIN/END)
- `@var` = variável de sessão (continua depois do CALL)
- `SELECT ... INTO var` = guarda resultado na variável
- `DELIMITER $$` = troca o `;` para o MySQL não achar que o comando acabou no meio

```sql
DELIMITER $$
CREATE PROCEDURE sp_nome(IN p_x INT, OUT p_qtd INT)
BEGIN
    DECLARE i INT DEFAULT 1;
    SELECT COUNT(*) INTO p_qtd FROM tabela WHERE campo = p_x;
    WHILE i <= 7 DO
        SET i = i + 1;
    END WHILE;
END $$
DELIMITER ;

CALL sp_nome(10, @qtd);
SELECT @qtd;
```

Outros laços: `REPEAT ... UNTIL cond END REPEAT;` e `LOOP` com `LEAVE`. Condição: `IF ... THEN ... ELSEIF ... ELSE ... END IF;`

## 2. Stored Function

Retorna sempre UM valor (`RETURNS tipo` + `RETURN`) e é usada dentro do SQL: SELECT, WHERE, GROUP BY, ORDER BY.

|  | Procedure | Function |
| --- | --- | --- |
| Chamada | `CALL sp()` | `SELECT fn(x)` |
| Retorno | nenhum, vários OUT, result sets | exatamente 1 valor |
| Usa no SELECT/WHERE | não | sim |
| COMMIT/ROLLBACK | pode | não pode |

Característica obrigatória (senão erro **1418**): `DETERMINISTIC` (mesma entrada, mesma saída), `READS SQL DATA` (lê tabelas) ou `NO SQL`.

```sql
DELIMITER $$
CREATE FUNCTION fn_nome(p_id INT)
RETURNS INT
READS SQL DATA
BEGIN
    DECLARE v INT DEFAULT 0;
    DECLARE CONTINUE HANDLER FOR NOT FOUND SET v = NULL;
    SELECT COUNT(*) INTO v FROM tabela WHERE id = p_id;
    RETURN v;
END $$
DELIMITER ;

SELECT nome, fn_nome(id) AS qtd FROM t WHERE fn_nome(id) >= 3;
```

Sem resultado: `RETURN IFNULL(v, 'Nenhuma');`. Empate: `ORDER BY COUNT(*) DESC, nome ASC LIMIT 1`.

## 3. Trigger

Código que dispara sozinho num evento da tabela; ninguém chama. Momento `BEFORE`/`AFTER` × evento `INSERT`/`UPDATE`/`DELETE` = 6 combinações, sempre `FOR EACH ROW`.

| Evento | OLD | NEW |
| --- | --- | --- |
| INSERT | não existe | linha nova |
| UPDATE | valor antigo | valor novo |
| DELETE | linha apagada | não existe |

- **BEFORE**: validar ou corrigir. Pode alterar `NEW` (`SET NEW.campo = ...`) e barrar com `SIGNAL`.
- **AFTER**: consequências (log, atualizar outra tabela). Não pode alterar `NEW`.
- Usos: auditoria/log, validação, padronização, manter totais sincronizados.
- Cuidado: são invisíveis, podem duplicar efeitos (trigger + procedure fazendo a mesma conta = contagem em dobro).
- BEFORE DELETE com SIGNAL roda antes da checagem de FK, por isso aparece a mensagem do trigger e não o erro 1451.

```sql
DELIMITER $$
CREATE TRIGGER trg_nome
BEFORE INSERT ON tabela
FOR EACH ROW
BEGIN
    SET NEW.nome = TRIM(NEW.nome);
    IF NEW.descricao IS NULL OR NEW.descricao = '' THEN
        SET NEW.descricao = CONCAT('Linha ', NEW.nome);
    END IF;
END $$

CREATE TRIGGER trg_log
AFTER UPDATE ON tabela
FOR EACH ROW
BEGIN
    IF NEW.campo <> OLD.campo THEN
        INSERT INTO log (id_reg, antes, depois, data)
        VALUES (NEW.id, OLD.campo, NEW.campo, NOW());
    END IF;
END $$
DELIMITER ;

DROP TRIGGER IF EXISTS trg_nome;
SHOW TRIGGERS;
```

## 4. Transações

Conjunto de operações tratado como uma unidade: ou tudo acontece, ou nada.

| ACID | Significado |
| --- | --- |
| **A**tomicidade | tudo ou nada |
| **C**onsistência | sai de um estado válido para outro (PK, FK, regras) |
| **I**solamento | uma transação não vê o que outra ainda não confirmou |
| **D**urabilidade | depois do COMMIT não se perde, nem se o servidor cair |

| Comando | Faz |
| --- | --- |
| `START TRANSACTION` | abre |
| `COMMIT` | confirma |
| `ROLLBACK` | desfaz tudo |
| `SAVEPOINT x` | marca um ponto |
| `ROLLBACK TO SAVEPOINT x` | desfaz só o que veio depois do ponto |
| `SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='...'` | gera erro próprio (45000 = erro do usuário) |
| `DECLARE EXIT HANDLER FOR SQLEXCEPTION` | o que fazer quando der erro (EXIT sai, CONTINUE segue) |
| `RESIGNAL` | repassa o erro original para quem chamou |

- Handler específico: `FOR 1452` (FK), `FOR NOT FOUND`, `FOR SQLSTATE '45000'`. `SQLEXCEPTION` pega todos.
- Autocommit: fora de transação cada comando já é confirmado.
- `CREATE`, `ALTER`, `DROP` fazem commit implícito (não dá ROLLBACK).
- O que o trigger faz entra na MESMA transação: o ROLLBACK desfaz o log do trigger também.
- `ROW_COUNT()` = linhas afetadas pelo último comando. Ler logo depois do UPDATE.

```sql
DELIMITER $$
CREATE PROCEDURE sp_x(IN p_id INT)
BEGIN
    DECLARE v INT DEFAULT 0;          -- 1º variáveis
    DECLARE EXIT HANDLER FOR SQLEXCEPTION   -- 2º handler
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    START TRANSACTION;
    UPDATE t SET ativo = 0 WHERE id = p_id AND ativo = 1;
    IF ROW_COUNT() = 0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Nada alterado';
    END IF;

    SAVEPOINT ponto;
    UPDATE t2 SET total = total * 1.1 WHERE id = p_id;
    IF (SELECT total FROM t2 WHERE id = p_id) > 1000 THEN
        ROLLBACK TO SAVEPOINT ponto;
    END IF;
    COMMIT;
END $$
DELIMITER ;
```

## 5. Big Data

Dados grandes, rápidos ou variados demais para o processamento tradicional.

| 5 Vs | Significado |
| --- | --- |
| Volume | quantidade enorme |
| Velocidade | gerados e processados rápido, até tempo real |
| Variedade | estruturado (tabela), semiestruturado (JSON, XML), não estruturado (texto, imagem, vídeo) |
| Veracidade | confiabilidade / qualidade (ex.: cidade com população 0) |
| Valor | o dado precisa gerar informação útil |

| NoSQL | Como guarda | Exemplo |
| --- | --- | --- |
| Chave-valor | chave aponta para um valor; simples e rápido (cache, sessão) | Redis, DynamoDB |
| Documento | JSON/BSON, estrutura flexível | MongoDB |
| Colunar | família de colunas, muita escrita e análise | Cassandra, HBase |
| Grafo | nós e relacionamentos (redes sociais, recomendação) | Neo4j |

- SQL: esquema fixo, ACID, escala **vertical** (máquina mais forte).
- NoSQL: esquema flexível, escala **horizontal** (mais máquinas).
- Teorema CAP: Consistência, Disponibilidade, Tolerância a partição. Quando a rede falha, escolhe C ou A.

```sql
CREATE TABLE kv (chave VARCHAR(20) PRIMARY KEY, valor JSON);

INSERT INTO kv (chave, valor)
SELECT CONCAT('pais:', Code), JSON_OBJECT('nome', Name, 'pop', Population)
  FROM world.country WHERE Continent = 'South America'
ON DUPLICATE KEY UPDATE valor = VALUES(valor);

SELECT valor->>'$.nome' AS nome FROM kv WHERE chave = 'pais:BRA';
```

`->>` devolve texto sem aspas; `->` devolve com aspas. Igual a `JSON_UNQUOTE(JSON_EXTRACT(valor,'$.nome'))`.

## 6. Engenharia de Dados

Constrói os pipelines que levam o dado da origem até onde ele é analisado.

1. **E**xtract: tirar da origem (tabela temporária de staging).
2. **T**ransform: limpar, padronizar (`UPPER`), filtrar (tirar 'Cancelled'), agregar.
3. **L**oad: carregar no destino (DW).

| Termo | Significado |
| --- | --- |
| ELT | carrega primeiro, transforma no destino (nuvem, data lake) |
| Staging | área temporária do dado bruto antes de transformar |
| Data Warehouse | banco para análise: histórico, integrado, agregado |
| Data Lake | guarda dado bruto em qualquer formato |
| OLTP | dia a dia, muitas transações pequenas |
| OLAP | análise, consultas grandes e agregadas |
| Idempotência | rodar 2 vezes dá o mesmo resultado (DELETE do período + INSERT, ou ON DUPLICATE KEY) |
| Snapshot | foto dos dados num momento; comparar com a origem mostra o que mudou |
| CDC | Change Data Capture: capturar só o que mudou (carga incremental) |
| Log de execução | registra OK/ERRO e linhas carregadas |

Qualidade: **veracidade** (dado verdadeiro?), **consistência** ('MG' x 'Minas Gerais'), **completude** (NULLs).

```sql
-- snapshot
CREATE TABLE dw.snap AS SELECT * FROM origem.t;
ALTER TABLE dw.snap ADD PRIMARY KEY (ID);

-- detectar alterações
SELECT s.ID, s.Pop AS antiga, o.Pop AS nova
  FROM dw.snap s JOIN origem.t o ON o.ID = s.ID
 WHERE s.Pop <> o.Pop OR s.District <> o.District;

-- staging
CREATE TEMPORARY TABLE stg AS SELECT ... WHERE YEAR(data) = p_ano;

-- ranking
SELECT * FROM (
  SELECT pais, receita, RANK() OVER (ORDER BY receita DESC) AS pos
    FROM vendas WHERE ano = 2004) t
 WHERE pos <= 3;
```

`RANK()` pula posição no empate (1,1,3); `DENSE_RANK()` não pula (1,1,2); `ROW_NUMBER()` nunca empata.

## 7. Pegadinhas e funções úteis

| Erro / situação | Causa / solução |
| --- | --- |
| 1418 | function sem DETERMINISTIC / READS SQL DATA |
| 1452 | FK: valor pai não existe (ex.: escritório '99') |
| 1451 | FK: apagar pai que tem filhos |
| 1062 | chave duplicada (PK/UNIQUE) |
| 1644 | erro gerado pelo SIGNAL (SQLSTATE 45000) |
| Syntax error no DECLARE | ordem: variáveis → cursores → handlers, tudo no início do BEGIN |
| Procedure não compila | esqueceu `DELIMITER $$` ou o `DELIMITER ;` no final |
| ROW\_COUNT() errado | algum comando entre o UPDATE e a leitura |
| Contagem em dobro | trigger e procedure atualizando o mesmo total |

- Sempre `DROP PROCEDURE/FUNCTION/TRIGGER IF EXISTS` antes de criar.
- Testar caso de sucesso E de falha.
- Ordem obrigatória no pedido do professor: fazer o UPDATE antes da verificação quando ele pedir (o handler desfaz).

| Função | Uso |
| --- | --- |
| `CONCAT(a, b)` | junta textos |
| `TRIM(x)` | tira espaços das pontas |
| `UPPER(x)` / `LOWER(x)` | maiúsculas / minúsculas |
| `IFNULL(x, padrao)` | troca NULL |
| `IF(cond, a, b)` | condicional inline |
| `ROUND(x, n)` | arredonda |
| `DATEDIFF(fim, inicio)` | dias entre datas |
| `YEAR(data)` / `NOW()` | ano / data e hora atual |
| `COUNT(DISTINCT x)` | conta sem repetir |
| `CAST(i AS CHAR)` | converte tipo |

# Exercícios resolvidos

Questões do simulado (Q01 a Q15) e exercícios extras (E1 a E12), todos testados no MySQL 8. Compare o enunciado da prova com o mais parecido daqui.

## Exercícios: Stored Procedures

### Q01 · Fácil · World

Procedure `sp_paises_regiao` recebe uma região e lista nome, área e população, da maior para a menor área.

```sql
USE world;
DROP PROCEDURE IF EXISTS sp_paises_regiao;
DELIMITER $$
CREATE PROCEDURE sp_paises_regiao(IN p_regiao VARCHAR(26))
BEGIN
    SELECT Name, SurfaceArea, Population
      FROM country
     WHERE Region = p_regiao
     ORDER BY SurfaceArea DESC;
END $$
DELIMITER ;

CALL sp_paises_regiao('Southern Europe');
```

Resultado: Spain primeiro (505992), Holy See por último (0.40). 15 países.

### Q02 · Intermediária · Sakila

Procedure `sp_filmes_categoria_preco` recebe categoria e rental\_rate, lista os filmes em ordem alfabética e devolve a quantidade num OUT.

```sql
USE sakila;
DROP PROCEDURE IF EXISTS sp_filmes_categoria_preco;
DELIMITER $$
CREATE PROCEDURE sp_filmes_categoria_preco(
    IN  p_categoria VARCHAR(25),
    IN  p_valor     DECIMAL(4,2),
    OUT p_qtd       INT)
BEGIN
    SELECT f.title, f.rental_rate
      FROM film f
      JOIN film_category fc ON fc.film_id = f.film_id
      JOIN category c       ON c.category_id = fc.category_id
     WHERE c.name = p_categoria AND f.rental_rate = p_valor
     ORDER BY f.title;

    SELECT COUNT(*) INTO p_qtd
      FROM film f
      JOIN film_category fc ON fc.film_id = f.film_id
      JOIN category c       ON c.category_id = fc.category_id
     WHERE c.name = p_categoria AND f.rental_rate = p_valor;
END $$
DELIMITER ;

CALL sp_filmes_categoria_preco('Horror', 4.99, @qtd);
SELECT @qtd;
```

Resultado: 21 filmes, `@qtd = 21`.

### Q03 · Difícil · ClassicModels

Procedure `sp_receita_escritorios` com WHILE de 1 a 7, soma pagamentos por escritório, monta texto 'Cidade: total | ...' e confere com o total de payments.

```sql
USE classicmodels;
DROP PROCEDURE IF EXISTS sp_receita_escritorios;
DELIMITER $$
CREATE PROCEDURE sp_receita_escritorios()
BEGIN
    DECLARE i        INT DEFAULT 1;
    DECLARE v_cidade VARCHAR(50);
    DECLARE v_total  DECIMAL(12,2);
    DECLARE v_soma   DECIMAL(12,2) DEFAULT 0;
    DECLARE v_texto  TEXT DEFAULT '';

    WHILE i <= 7 DO
        SELECT city INTO v_cidade FROM offices WHERE officeCode = CAST(i AS CHAR);

        SELECT IFNULL(SUM(p.amount), 0) INTO v_total
          FROM payments p
          JOIN customers c ON c.customerNumber = p.customerNumber
          JOIN employees e ON e.employeeNumber = c.salesRepEmployeeNumber
         WHERE e.officeCode = CAST(i AS CHAR);

        SET v_texto = CONCAT(v_texto, IF(i > 1, ' | ', ''), v_cidade, ': ', v_total);
        SET v_soma = v_soma + v_total;
        SET i = i + 1;
    END WHILE;

    SELECT v_texto AS receita_por_escritorio;
    SELECT v_soma AS soma_escritorios,
           (SELECT SUM(amount) FROM payments) AS soma_payments,
           IF(v_soma = (SELECT SUM(amount) FROM payments), 'Confere', 'Diferente') AS conferencia;
END $$
DELIMITER ;

CALL sp_receita_escritorios();
```

Resultado: San Francisco 1337439.58 | Boston 835882.33 | NYC 1072619.47 | Paris 2819168.90 | Tokyo 457110.07 | Sydney 1007292.98 | London 1324325.90. Soma 8853839.23 = Confere.

### E1 · Parâmetro INOUT · ClassicModels

Procedure `sp_aplica_desconto` recebe um valor (INOUT) e um percentual, e devolve o valor com desconto na mesma variável.

```sql
DROP PROCEDURE IF EXISTS sp_aplica_desconto;
DELIMITER $$
CREATE PROCEDURE sp_aplica_desconto(INOUT p_valor DECIMAL(10,2), IN p_percentual INT)
BEGIN
    SET p_valor = ROUND(p_valor * (1 - p_percentual / 100), 2);
END $$
DELIMITER ;

SET @preco = 200.00;
CALL sp_aplica_desconto(@preco, 15);
SELECT @preco;   -- 170.00
```

### E2 · Cursor · ClassicModels

Procedure `sp_lista_cidades_escritorios` percorre os escritórios com CURSOR e monta uma lista separada por vírgula.

```sql
DROP PROCEDURE IF EXISTS sp_lista_cidades_escritorios;
DELIMITER $$
CREATE PROCEDURE sp_lista_cidades_escritorios()
BEGIN
    DECLARE v_cidade VARCHAR(50);          -- 1º variáveis
    DECLARE v_fim INT DEFAULT 0;
    DECLARE v_lista TEXT DEFAULT '';
    DECLARE cur CURSOR FOR SELECT city FROM offices ORDER BY city;   -- 2º cursor
    DECLARE CONTINUE HANDLER FOR NOT FOUND SET v_fim = 1;           -- 3º handler

    OPEN cur;
    ler: LOOP
        FETCH cur INTO v_cidade;
        IF v_fim = 1 THEN
            LEAVE ler;
        END IF;
        SET v_lista = CONCAT(v_lista, IF(v_lista = '', '', ', '), v_cidade);
    END LOOP;
    CLOSE cur;

    SELECT v_lista AS cidades;
END $$
DELIMITER ;

CALL sp_lista_cidades_escritorios();
```

Resultado: Boston, London, NYC, Paris, San Francisco, Sydney, Tokyo.

### E3 · REPEAT + OUT · Sakila

Procedure `sp_filmes_por_duracao` conta filmes em faixas de 60 minutos (até 180) com REPEAT e devolve um texto num OUT.

```sql
USE sakila;
DROP PROCEDURE IF EXISTS sp_filmes_por_duracao;
DELIMITER $$
CREATE PROCEDURE sp_filmes_por_duracao(OUT p_resumo TEXT)
BEGIN
    DECLARE v_min INT DEFAULT 0;
    DECLARE v_qtd INT;
    SET p_resumo = '';
    REPEAT
        SELECT COUNT(*) INTO v_qtd FROM film
         WHERE length > v_min AND length <= v_min + 60;
        SET p_resumo = CONCAT(p_resumo, IF(v_min > 0, ' | ', ''),
                              v_min + 1, '-', v_min + 60, ' min: ', v_qtd);
        SET v_min = v_min + 60;
    UNTIL v_min >= 180 END REPEAT;
END $$
DELIMITER ;

CALL sp_filmes_por_duracao(@r);
SELECT @r;
```

Resultado: 1-60 min: 104 | 61-120 min: 439 | 121-180 min: 418.

WHILE testa antes (pode não rodar nenhuma vez); REPEAT testa depois (roda pelo menos 1 vez); LOOP precisa de LEAVE para sair.

## Exercícios: Stored Functions

### Q04 · Fácil · ClassicModels

Function `fn_dias_entrega` recebe o pedido e retorna os dias entre orderDate e shippedDate (NULL se não enviado). Listar os 5 maiores prazos.

```sql
USE classicmodels;
DROP FUNCTION IF EXISTS fn_dias_entrega;
DELIMITER $$
CREATE FUNCTION fn_dias_entrega(p_pedido INT)
RETURNS INT
READS SQL DATA
BEGIN
    DECLARE v_dias INT DEFAULT NULL;
    SELECT DATEDIFF(shippedDate, orderDate) INTO v_dias
      FROM orders WHERE orderNumber = p_pedido;
    RETURN v_dias;
END $$
DELIMITER ;

SELECT orderNumber, orderDate, shippedDate, fn_dias_entrega(orderNumber) AS dias
  FROM orders
 ORDER BY dias DESC, orderNumber ASC
 LIMIT 5;
```

Resultado: 10165 (65 dias), 10210 (8), 10258 (8), 10240 (7), 10339 (7). Comentário: o 10165 é um valor muito fora do normal.

### Q05 · Intermediária · World

Function `fn_qtd_idiomas_oficiais` retorna quantos idiomas oficiais o país tem. Usar no WHERE para países com 3 ou mais.

```sql
USE world;
DROP FUNCTION IF EXISTS fn_qtd_idiomas_oficiais;
DELIMITER $$
CREATE FUNCTION fn_qtd_idiomas_oficiais(p_pais CHAR(3))
RETURNS INT
READS SQL DATA
BEGIN
    DECLARE v_qtd INT DEFAULT 0;
    SELECT COUNT(*) INTO v_qtd
      FROM countrylanguage
     WHERE CountryCode = p_pais AND IsOfficial = 'T';
    RETURN v_qtd;
END $$
DELIMITER ;

SELECT Code, Name, fn_qtd_idiomas_oficiais(Code) AS qtd_oficiais
  FROM country
 WHERE fn_qtd_idiomas_oficiais(Code) >= 3
 ORDER BY qtd_oficiais DESC, Name ASC;
```

Resultado: South Africa e Switzerland (4); Belgium, Bolivia, Luxembourg, Peru, Singapore, Vanuatu (3).

### Q06 · Difícil · Sakila

Function `fn_categoria_favorita` retorna a categoria mais alugada pelo cliente (empate: menor nome; sem locação: 'Nenhuma'). Mostrar clientes 1 a 5 e as 3 favoritas mais comuns.

```sql
USE sakila;
DROP FUNCTION IF EXISTS fn_categoria_favorita;
DELIMITER $$
CREATE FUNCTION fn_categoria_favorita(p_cliente INT)
RETURNS VARCHAR(25)
READS SQL DATA
BEGIN
    DECLARE v_categoria VARCHAR(25) DEFAULT NULL;
    DECLARE CONTINUE HANDLER FOR NOT FOUND SET v_categoria = NULL;

    SELECT c.name INTO v_categoria
      FROM rental r
      JOIN inventory i      ON i.inventory_id = r.inventory_id
      JOIN film_category fc ON fc.film_id     = i.film_id
      JOIN category c       ON c.category_id  = fc.category_id
     WHERE r.customer_id = p_cliente
     GROUP BY c.category_id, c.name
     ORDER BY COUNT(*) DESC, c.name ASC
     LIMIT 1;

    RETURN IFNULL(v_categoria, 'Nenhuma');
END $$
DELIMITER ;

SELECT customer_id, first_name, fn_categoria_favorita(customer_id) AS favorita
  FROM customer WHERE customer_id BETWEEN 1 AND 5;

SELECT fn_categoria_favorita(customer_id) AS categoria, COUNT(*) AS qtd_clientes
  FROM customer
 GROUP BY categoria
 ORDER BY qtd_clientes DESC, categoria ASC
 LIMIT 3;
```

Resultado: 1 Classics, 2 Sports, 3 Action, 4 Horror, 5 Classics. Top 3: Animation (82), Action (80), Sci-Fi (53).

### E4 · Function com SUM · ClassicModels

Function `fn_total_pedido` retorna o valor total do pedido (soma de quantityOrdered × priceEach). Listar os 3 maiores pedidos.

```sql
USE classicmodels;
DROP FUNCTION IF EXISTS fn_total_pedido;
DELIMITER $$
CREATE FUNCTION fn_total_pedido(p_pedido INT)
RETURNS DECIMAL(12,2)
READS SQL DATA
BEGIN
    DECLARE v_total DECIMAL(12,2);
    SELECT SUM(quantityOrdered * priceEach) INTO v_total
      FROM orderdetails WHERE orderNumber = p_pedido;
    RETURN IFNULL(v_total, 0);
END $$
DELIMITER ;

SELECT orderNumber, fn_total_pedido(orderNumber) AS total
  FROM orders ORDER BY total DESC LIMIT 3;
```

Resultado: 10165 (67392.85), 10287 (61402.00), 10310 (61234.67).

### E5 · Function DETERMINISTIC com CASE + GROUP BY · ClassicModels

Function `fn_faixa_credito` recebe um limite de crédito e retorna a faixa. Não lê tabela, então é DETERMINISTIC. Agrupar os clientes pela faixa.

```sql
DROP FUNCTION IF EXISTS fn_faixa_credito;
DELIMITER $$
CREATE FUNCTION fn_faixa_credito(p_limite DECIMAL(10,2))
RETURNS VARCHAR(15)
DETERMINISTIC
BEGIN
    RETURN CASE
        WHEN p_limite = 0      THEN 'Sem crédito'
        WHEN p_limite < 50000  THEN 'Baixo'
        WHEN p_limite < 100000 THEN 'Médio'
        ELSE 'Alto'
    END;
END $$
DELIMITER ;

SELECT fn_faixa_credito(creditLimit) AS faixa, COUNT(*) AS clientes
  FROM customers GROUP BY faixa ORDER BY clientes DESC;
```

Resultado: Médio 60, Alto 25, Sem crédito 23, Baixo 13. Cuidado: o tamanho do VARCHAR do RETURNS tem que caber o maior texto (erro 1406 se não couber).

## Exercícios: Triggers

### Q07 · Fácil · ClassicModels

Trigger `trg_padroniza_linha` BEFORE INSERT em productlines: TRIM no nome e, se a descrição vier vazia, preencher com 'Linha \<nome> (descrição pendente)'.

```sql
USE classicmodels;
DROP TRIGGER IF EXISTS trg_padroniza_linha;
DELIMITER $$
CREATE TRIGGER trg_padroniza_linha
BEFORE INSERT ON productlines
FOR EACH ROW
BEGIN
    SET NEW.productLine = TRIM(NEW.productLine);
    IF NEW.textDescription IS NULL OR TRIM(NEW.textDescription) = '' THEN
        SET NEW.textDescription = CONCAT('Linha ', NEW.productLine, ' (descrição pendente)');
    END IF;
END $$
DELIMITER ;

INSERT INTO productlines (productLine) VALUES ('Bicycles ');
INSERT INTO productlines (productLine, textDescription)
VALUES ('Tractors', 'Tratores agrícolas em miniatura');

SELECT productLine, CHAR_LENGTH(productLine) AS tamanho, textDescription
  FROM productlines WHERE productLine IN ('Bicycles', 'Tractors');
```

Resultado: 'Bicycles' com 8 caracteres e 'Linha Bicycles (descrição pendente)'; Tractors mantém a descrição.

### Q08 · Intermediária · ClassicModels

Trigger `trg_protege_cliente` BEFORE DELETE em customers: conta os pedidos e barra com SIGNAL se tiver algum.

```sql
DROP TRIGGER IF EXISTS trg_protege_cliente;
DELIMITER $$
CREATE TRIGGER trg_protege_cliente
BEFORE DELETE ON customers
FOR EACH ROW
BEGIN
    DECLARE v_pedidos INT DEFAULT 0;
    SELECT COUNT(*) INTO v_pedidos FROM orders WHERE customerNumber = OLD.customerNumber;
    IF v_pedidos > 0 THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Cliente possui pedidos e não pode ser excluído';
    END IF;
END $$
DELIMITER ;

DELETE FROM customers WHERE customerNumber = 103;  -- erro do trigger
DELETE FROM customers WHERE customerNumber = 125;  -- apaga
```

Por que a mensagem do trigger e não o erro de FK: o BEFORE roda antes da exclusão; a FK só seria checada na exclusão, mas o SIGNAL cancela antes.

### Q09 · Difícil · World

Trigger `trg_sincroniza_pop_pais` AFTER UPDATE em city: soma ao país a diferença NEW − OLD da população, só se ela mudou.

```sql
USE world;
DROP TRIGGER IF EXISTS trg_sincroniza_pop_pais;
DELIMITER $$
CREATE TRIGGER trg_sincroniza_pop_pais
AFTER UPDATE ON city
FOR EACH ROW
BEGIN
    IF NEW.Population <> OLD.Population THEN
        UPDATE country
           SET Population = Population + (NEW.Population - OLD.Population)
         WHERE Code = NEW.CountryCode;
    END IF;
END $$
DELIMITER ;

SELECT Population INTO @pop_antes FROM country WHERE Code = 'BRA';
UPDATE city SET Population = Population + 1000 WHERE Name = 'Belo Horizonte' AND CountryCode = 'BRA';
UPDATE city SET Population = Population - 300  WHERE Name = 'Contagem' AND CountryCode = 'BRA';
UPDATE city SET District = 'MG'                WHERE Name = 'Betim' AND CountryCode = 'BRA';
SELECT Population - @pop_antes AS diferenca FROM country WHERE Code = 'BRA';   -- 700
```

### E6 · BEFORE UPDATE com validação e correção · ClassicModels

Trigger `trg_valida_preco` em products: barra se buyPrice ficar maior que MSRP e troca estoque negativo por 0.

```sql
DROP TRIGGER IF EXISTS trg_valida_preco;
DELIMITER $$
CREATE TRIGGER trg_valida_preco
BEFORE UPDATE ON products
FOR EACH ROW
BEGIN
    IF NEW.buyPrice > NEW.MSRP THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Preço de compra maior que o preço de venda';
    END IF;
    IF NEW.quantityInStock < 0 THEN
        SET NEW.quantityInStock = 0;
    END IF;
END $$
DELIMITER ;

UPDATE products SET buyPrice = MSRP + 1   WHERE productCode = 'S10_1678';  -- erro
UPDATE products SET quantityInStock = -5 WHERE productCode = 'S10_1678';  -- vira 0
```

### E7 · AFTER DELETE com log · World

Tabela `cidade_excluida` e trigger `trg_log_cidade_excluida` que guarda os dados da cidade apagada (usa OLD).

```sql
USE world;
CREATE TABLE cidade_excluida (
    id INT AUTO_INCREMENT PRIMARY KEY,
    city_id INT, nome VARCHAR(35), pais CHAR(3),
    populacao INT, excluida_em DATETIME);

DROP TRIGGER IF EXISTS trg_log_cidade_excluida;
DELIMITER $$
CREATE TRIGGER trg_log_cidade_excluida
AFTER DELETE ON city
FOR EACH ROW
BEGIN
    INSERT INTO cidade_excluida (city_id, nome, pais, populacao, excluida_em)
    VALUES (OLD.ID, OLD.Name, OLD.CountryCode, OLD.Population, NOW());
END $$
DELIMITER ;

INSERT INTO city (Name, CountryCode, District, Population) VALUES ('Cidade Teste', 'BRA', 'MG', 100);
DELETE FROM city WHERE Name = 'Cidade Teste';
SELECT * FROM cidade_excluida;   -- 1 linha
```

No DELETE só existe OLD; no INSERT só NEW. Usar NEW num trigger de DELETE dá erro.

## Exercícios: Transações

### Q10 · Difícil · Sakila

Tabela de log + trigger AFTER UPDATE em customer + procedure `sp_desativar_cliente` que desativa, checa ROW\_COUNT e locações em aberto. O handler desfaz o UPDATE e o log do trigger.

```sql
USE sakila;
CREATE TABLE cliente_status_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    customer_id INT, ativo_antes TINYINT, ativo_depois TINYINT, alterado_em DATETIME);

DROP TRIGGER IF EXISTS trg_log_status_cliente;
DELIMITER $$
CREATE TRIGGER trg_log_status_cliente
AFTER UPDATE ON customer
FOR EACH ROW
BEGIN
    IF NEW.active <> OLD.active THEN
        INSERT INTO cliente_status_log (customer_id, ativo_antes, ativo_depois, alterado_em)
        VALUES (NEW.customer_id, OLD.active, NEW.active, NOW());
    END IF;
END $$

DROP PROCEDURE IF EXISTS sp_desativar_cliente $$
CREATE PROCEDURE sp_desativar_cliente(IN p_cliente INT)
BEGIN
    DECLARE v_abertas INT DEFAULT 0;
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    START TRANSACTION;
    UPDATE customer SET active = 0 WHERE customer_id = p_cliente AND active = 1;
    IF ROW_COUNT() = 0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Cliente inexistente ou já inativo';
    END IF;

    SELECT COUNT(*) INTO v_abertas FROM rental
     WHERE customer_id = p_cliente AND return_date IS NULL;
    IF v_abertas > 0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Cliente com filmes não devolvidos';
    END IF;
    COMMIT;
END $$
DELIMITER ;

CALL sp_desativar_cliente(1);   -- ok
CALL sp_desativar_cliente(5);   -- erro: filmes não devolvidos
CALL sp_desativar_cliente(1);   -- erro: já inativo
SELECT * FROM cliente_status_log;   -- 1 linha
```

### Q11 · Difícil · ClassicModels

Tabela + trigger de log de officeCode + procedure `sp_transferir_funcionario`. Gerente (tem subordinado) não pode ser transferido; escritório inexistente gera erro 1452. Os dois caem no mesmo handler.

```sql
USE classicmodels;
CREATE TABLE transferencia_funcionario (
    id INT AUTO_INCREMENT PRIMARY KEY,
    employeeNumber INT, escritorio_antigo VARCHAR(10),
    escritorio_novo VARCHAR(10), transferido_em DATETIME);

DROP TRIGGER IF EXISTS trg_log_escritorio;
DELIMITER $$
CREATE TRIGGER trg_log_escritorio
AFTER UPDATE ON employees
FOR EACH ROW
BEGIN
    IF NEW.officeCode <> OLD.officeCode THEN
        INSERT INTO transferencia_funcionario
               (employeeNumber, escritorio_antigo, escritorio_novo, transferido_em)
        VALUES (NEW.employeeNumber, OLD.officeCode, NEW.officeCode, NOW());
    END IF;
END $$

DROP PROCEDURE IF EXISTS sp_transferir_funcionario $$
CREATE PROCEDURE sp_transferir_funcionario(IN p_funcionario INT, IN p_escritorio VARCHAR(10))
BEGIN
    DECLARE v_subordinados INT DEFAULT 0;
    DECLARE EXIT HANDLER FOR SQLEXCEPTION   -- pega SIGNAL e 1452
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    START TRANSACTION;
    UPDATE employees SET officeCode = p_escritorio WHERE employeeNumber = p_funcionario;
    SELECT COUNT(*) INTO v_subordinados FROM employees WHERE reportsTo = p_funcionario;
    IF v_subordinados > 0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Gerentes não podem ser transferidos';
    END IF;
    COMMIT;
END $$
DELIMITER ;

CALL sp_transferir_funcionario(1165, '4');   -- ok
CALL sp_transferir_funcionario(1143, '4');   -- erro: gerente
CALL sp_transferir_funcionario(1166, '99');  -- erro 1452
SELECT * FROM transferencia_funcionario;     -- 1 linha
```

Se o professor pedir handler específico: `DECLARE EXIT HANDLER FOR SQLSTATE '45000', 1452`.

### Q12 · Difícil · World (SAVEPOINT)

Remover o trigger da Q09 (senão o país conta em dobro: o trigger soma a diferença das cidades e a procedure aumenta o país de novo). Procedure `sp_aplicar_censo` aumenta cidades e país; se o país passar de 2 bilhões, volta ao savepoint.

```sql
USE world;
DROP TRIGGER IF EXISTS trg_sincroniza_pop_pais;

CREATE TABLE censo_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    CountryCode CHAR(3), percentual DECIMAL(5,2),
    situacao VARCHAR(60), registrado_em DATETIME);

DROP PROCEDURE IF EXISTS sp_aplicar_censo;
DELIMITER $$
CREATE PROCEDURE sp_aplicar_censo(IN p_pais CHAR(3), IN p_percentual DECIMAL(5,2))
BEGIN
    DECLARE v_nova_pop BIGINT;
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    IF p_percentual <= 0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Percentual deve ser positivo';
    END IF;

    START TRANSACTION;
    UPDATE city SET Population = ROUND(Population * (1 + p_percentual / 100))
     WHERE CountryCode = p_pais;
    IF ROW_COUNT() = 0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'País sem cidades cadastradas';
    END IF;

    SAVEPOINT apos_cidades;

    UPDATE country SET Population = ROUND(Population * (1 + p_percentual / 100))
     WHERE Code = p_pais;
    SELECT Population INTO v_nova_pop FROM country WHERE Code = p_pais;

    IF v_nova_pop > 2000000000 THEN
        ROLLBACK TO SAVEPOINT apos_cidades;
        INSERT INTO censo_log (CountryCode, percentual, situacao, registrado_em)
        VALUES (p_pais, p_percentual, 'Somente cidades atualizadas', NOW());
    ELSE
        INSERT INTO censo_log (CountryCode, percentual, situacao, registrado_em)
        VALUES (p_pais, p_percentual, 'Cidades e país atualizados', NOW());
    END IF;
    COMMIT;
END $$
DELIMITER ;

CALL sp_aplicar_censo('BRA', 5);    -- tudo
CALL sp_aplicar_censo('CHN', 60);   -- só cidades
CALL sp_aplicar_censo('ATA', 10);   -- erro
```

### E8 · Transferência entre dois registros · ClassicModels

Procedure `sp_transferir_credito(origem, destino, valor)`: tira o crédito de um cliente e passa para outro. Erro se origem não existe, saldo fica negativo ou destino não existe. Exemplo clássico de atomicidade (tudo ou nada).

```sql
USE classicmodels;
DROP PROCEDURE IF EXISTS sp_transferir_credito;
DELIMITER $$
CREATE PROCEDURE sp_transferir_credito(IN p_origem INT, IN p_destino INT, IN p_valor DECIMAL(10,2))
BEGIN
    DECLARE v_saldo DECIMAL(10,2);
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    START TRANSACTION;

    UPDATE customers SET creditLimit = creditLimit - p_valor WHERE customerNumber = p_origem;
    IF ROW_COUNT() = 0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Cliente de origem não existe';
    END IF;

    SELECT creditLimit INTO v_saldo FROM customers WHERE customerNumber = p_origem;
    IF v_saldo < 0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Crédito insuficiente';
    END IF;

    UPDATE customers SET creditLimit = creditLimit + p_valor WHERE customerNumber = p_destino;
    IF ROW_COUNT() = 0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Cliente de destino não existe';
    END IF;

    COMMIT;
END $$
DELIMITER ;

CALL sp_transferir_credito(112, 114, 1000);     -- ok: 112 71800 -> 70800, 114 117300 -> 118300
CALL sp_transferir_credito(112, 114, 999999);   -- erro: Crédito insuficiente
CALL sp_transferir_credito(112, 9999, 10);      -- erro: destino não existe (a retirada é desfeita)
```

### E9 · SAVEPOINT com UPDATE + JOIN · Sakila

Procedure `sp_reajustar_categoria(categoria, percentual)`: reajusta rental\_rate dos filmes da categoria; depois do SAVEPOINT reajusta replacement\_cost. Se a média do replacement\_cost passar de 25, volta ao savepoint (só o aluguel fica).

```sql
USE sakila;
CREATE TABLE reajuste_log (id INT AUTO_INCREMENT PRIMARY KEY, categoria VARCHAR(25),
    percentual DECIMAL(5,2), situacao VARCHAR(40), registrado_em DATETIME);

DROP PROCEDURE IF EXISTS sp_reajustar_categoria;
DELIMITER $$
CREATE PROCEDURE sp_reajustar_categoria(IN p_categoria VARCHAR(25), IN p_percentual DECIMAL(5,2))
BEGIN
    DECLARE v_media DECIMAL(6,2);
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    START TRANSACTION;

    UPDATE film f
      JOIN film_category fc ON fc.film_id = f.film_id
      JOIN category c       ON c.category_id = fc.category_id
       SET f.rental_rate = ROUND(f.rental_rate * (1 + p_percentual / 100), 2)
     WHERE c.name = p_categoria;
    IF ROW_COUNT() = 0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Categoria inexistente';
    END IF;

    SAVEPOINT apos_aluguel;

    UPDATE film f
      JOIN film_category fc ON fc.film_id = f.film_id
      JOIN category c       ON c.category_id = fc.category_id
       SET f.replacement_cost = ROUND(f.replacement_cost * (1 + p_percentual / 100), 2)
     WHERE c.name = p_categoria;

    SELECT AVG(f.replacement_cost) INTO v_media
      FROM film f
      JOIN film_category fc ON fc.film_id = f.film_id
      JOIN category c       ON c.category_id = fc.category_id
     WHERE c.name = p_categoria;

    IF v_media > 25 THEN
        ROLLBACK TO SAVEPOINT apos_aluguel;
        INSERT INTO reajuste_log (categoria, percentual, situacao, registrado_em)
        VALUES (p_categoria, p_percentual, 'Só aluguel reajustado', NOW());
    ELSE
        INSERT INTO reajuste_log (categoria, percentual, situacao, registrado_em)
        VALUES (p_categoria, p_percentual, 'Aluguel e reposição reajustados', NOW());
    END IF;
    COMMIT;
END $$
DELIMITER ;

CALL sp_reajustar_categoria('Music', 5);    -- os dois reajustados
CALL sp_reajustar_categoria('Games', 30);   -- só aluguel
CALL sp_reajustar_categoria('Novela', 10);  -- erro: Categoria inexistente
```

O SIGNAL que vem antes do START TRANSACTION (como o do percentual na Q12) também cai no handler; o ROLLBACK ali não tem nada para desfazer, e está tudo bem.

## Exercícios: Big Data e Engenharia de Dados

### Q13 · Fácil · World (chave-valor)

Schema dw\_world, tabela kv\_pais, carga com INSERT ... SELECT + ON DUPLICATE KEY UPDATE, chave 'pais:\<Code>', leitura com ->>.

```sql
CREATE SCHEMA IF NOT EXISTS dw_world;
USE dw_world;
CREATE TABLE kv_pais (chave VARCHAR(20) PRIMARY KEY, valor JSON);

INSERT INTO kv_pais (chave, valor)
SELECT CONCAT('pais:', Code),
       JSON_OBJECT('nome', Name, 'populacao', Population, 'expectativa', LifeExpectancy)
  FROM world.country
 WHERE Continent = 'South America'
ON DUPLICATE KEY UPDATE valor = VALUES(valor);

SELECT chave, valor->>'$.nome' AS nome, valor->>'$.populacao' AS populacao
  FROM kv_pais WHERE chave = 'pais:BRA';
```

### Q14 · Intermediária · World (snapshot + veracidade)

```sql
CREATE SCHEMA IF NOT EXISTS origem_world;
CREATE TABLE origem_world.cidade_br AS
SELECT ID, Name, District, Population FROM world.city WHERE CountryCode = 'BRA';
ALTER TABLE origem_world.cidade_br ADD PRIMARY KEY (ID);

CREATE TABLE dw_world.cidade_br_snapshot AS SELECT * FROM origem_world.cidade_br;
ALTER TABLE dw_world.cidade_br_snapshot ADD PRIMARY KEY (ID);

UPDATE origem_world.cidade_br SET Population = Population + 5000 WHERE Name = 'Uberlândia';
UPDATE origem_world.cidade_br SET District = 'MG'                WHERE Name = 'Juiz de Fora';
UPDATE origem_world.cidade_br SET Population = 0                 WHERE Name = 'Sabará';

SELECT s.ID, s.Name,
       s.Population AS pop_antiga,      o.Population AS pop_nova,
       s.District   AS distrito_antigo, o.District   AS distrito_novo
  FROM dw_world.cidade_br_snapshot s
  JOIN origem_world.cidade_br o ON o.ID = s.ID
 WHERE s.Population <> o.Population OR s.District <> o.District;
```

Resultado: 3 linhas. Suspeita (veracidade): Sabará com população 0. 'MG' é só padronização (consistência).

### Q15 · Difícil · ClassicModels (ETL)

```sql
CREATE SCHEMA IF NOT EXISTS dw_classicmodels;
USE dw_classicmodels;
CREATE TABLE vendas_pais_ano (pais VARCHAR(50), ano INT, pedidos INT,
    receita DECIMAL(14,2), PRIMARY KEY (pais, ano));
CREATE TABLE etl_execucao (id INT AUTO_INCREMENT PRIMARY KEY, ano INT, linhas INT,
    situacao VARCHAR(10), executado_em DATETIME);

DROP PROCEDURE IF EXISTS sp_etl_vendas_pais;
DELIMITER $$
CREATE PROCEDURE sp_etl_vendas_pais(IN p_ano INT)
BEGIN
    DECLARE v_linhas INT DEFAULT 0;
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        INSERT INTO etl_execucao (ano, linhas, situacao, executado_em)
        VALUES (p_ano, 0, 'ERRO', NOW());
        RESIGNAL;
    END;

    -- E
    DROP TEMPORARY TABLE IF EXISTS stg_vendas;
    CREATE TEMPORARY TABLE stg_vendas AS
    SELECT c.country AS pais, o.orderNumber AS pedido,
           od.quantityOrdered * od.priceEach AS valor
      FROM classicmodels.orders o
      JOIN classicmodels.customers c     ON c.customerNumber = o.customerNumber
      JOIN classicmodels.orderdetails od ON od.orderNumber   = o.orderNumber
     WHERE YEAR(o.orderDate) = p_ano AND o.status <> 'Cancelled';

    -- T e L
    START TRANSACTION;
    DELETE FROM vendas_pais_ano WHERE ano = p_ano;
    INSERT INTO vendas_pais_ano (pais, ano, pedidos, receita)
    SELECT UPPER(pais), p_ano, COUNT(DISTINCT pedido), SUM(valor)
      FROM stg_vendas GROUP BY UPPER(pais);
    SET v_linhas = ROW_COUNT();
    IF v_linhas = 0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Nenhuma venda encontrada para o ano';
    END IF;
    INSERT INTO etl_execucao (ano, linhas, situacao, executado_em)
    VALUES (p_ano, v_linhas, 'OK', NOW());
    COMMIT;
END $$
DELIMITER ;

CALL sp_etl_vendas_pais(2004);
CALL sp_etl_vendas_pais(2004);   -- não duplica
CALL sp_etl_vendas_pais(1999);   -- erro, log 'ERRO'

SELECT * FROM (
  SELECT pais, pedidos, receita, RANK() OVER (ORDER BY receita DESC) AS posicao
    FROM vendas_pais_ano WHERE ano = 2004) t
 WHERE posicao <= 3;
```

Resultado: 20 países em 2004. Top 3: USA 1485054.44, FRANCE 506660.01, SPAIN 392816.48. O INSERT do 'ERRO' fica depois do ROLLBACK para não ser desfeito.

### E10 · Chave-valor com lista JSON · Sakila

Guardar por categoria a quantidade de filmes e a lista de títulos (JSON\_ARRAYAGG). Ler o tamanho da lista e o primeiro item.

```sql
CREATE SCHEMA IF NOT EXISTS dw_sakila;
USE dw_sakila;
CREATE TABLE kv_categoria (chave VARCHAR(30) PRIMARY KEY, valor JSON);

INSERT INTO kv_categoria (chave, valor)
SELECT CONCAT('categoria:', c.name),
       JSON_OBJECT('qtd_filmes', COUNT(*), 'filmes', JSON_ARRAYAGG(f.title))
  FROM sakila.category c
  JOIN sakila.film_category fc ON fc.category_id = c.category_id
  JOIN sakila.film f           ON f.film_id = fc.film_id
 GROUP BY c.name
ON DUPLICATE KEY UPDATE valor = VALUES(valor);

SELECT chave,
       valor->>'$.qtd_filmes'         AS qtd,
       JSON_LENGTH(valor->'$.filmes') AS tamanho_lista,
       valor->>'$.filmes[0]'          AS primeiro_filme
  FROM kv_categoria WHERE chave = 'categoria:Horror';
```

Resultado: 56, 56, ACE GOLDFINGER. Arrays começam no índice 0.

### E11 · Snapshot: novos, excluídos e alterados · ClassicModels

```sql
CREATE SCHEMA IF NOT EXISTS origem_classic;
CREATE SCHEMA IF NOT EXISTS dw_classicmodels;
CREATE TABLE origem_classic.escritorio AS
SELECT officeCode, city, country FROM classicmodels.offices;
ALTER TABLE origem_classic.escritorio ADD PRIMARY KEY (officeCode);
CREATE TABLE dw_classicmodels.escritorio_snapshot AS SELECT * FROM origem_classic.escritorio;
ALTER TABLE dw_classicmodels.escritorio_snapshot ADD PRIMARY KEY (officeCode);

INSERT INTO origem_classic.escritorio VALUES ('8', 'Belo Horizonte', 'Brazil');
DELETE FROM origem_classic.escritorio WHERE officeCode = '7';
UPDATE origem_classic.escritorio SET city = 'New York' WHERE officeCode = '3';

-- novos: estão na origem e não no snapshot
SELECT 'NOVO' AS tipo, o.officeCode, o.city
  FROM origem_classic.escritorio o
  LEFT JOIN dw_classicmodels.escritorio_snapshot s ON s.officeCode = o.officeCode
 WHERE s.officeCode IS NULL
UNION ALL
-- excluídos: estão no snapshot e não na origem
SELECT 'EXCLUIDO', s.officeCode, s.city
  FROM dw_classicmodels.escritorio_snapshot s
  LEFT JOIN origem_classic.escritorio o ON o.officeCode = s.officeCode
 WHERE o.officeCode IS NULL
UNION ALL
-- alterados: nos dois, com valor diferente
SELECT 'ALTERADO', o.officeCode, CONCAT(s.city, ' -> ', o.city)
  FROM origem_classic.escritorio o
  JOIN dw_classicmodels.escritorio_snapshot s ON s.officeCode = o.officeCode
 WHERE o.city <> s.city OR o.country <> s.country;
```

Resultado: NOVO 8 Belo Horizonte, EXCLUIDO 7 London, ALTERADO 3 NYC -> New York.

### E12 · ETL receita por mês · Sakila

```sql
USE dw_sakila;
CREATE TABLE receita_mes (ano INT, mes INT, locacoes INT, receita DECIMAL(10,2),
    PRIMARY KEY (ano, mes));
CREATE TABLE etl_log (id INT AUTO_INCREMENT PRIMARY KEY, ano INT, linhas INT,
    situacao VARCHAR(10), executado_em DATETIME);

DROP PROCEDURE IF EXISTS sp_etl_receita_mes;
DELIMITER $$
CREATE PROCEDURE sp_etl_receita_mes(IN p_ano INT)
BEGIN
    DECLARE v_linhas INT DEFAULT 0;
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        INSERT INTO etl_log (ano, linhas, situacao, executado_em) VALUES (p_ano, 0, 'ERRO', NOW());
        RESIGNAL;
    END;

    DROP TEMPORARY TABLE IF EXISTS stg_pagamentos;
    CREATE TEMPORARY TABLE stg_pagamentos AS
    SELECT MONTH(payment_date) AS mes, rental_id, amount
      FROM sakila.payment WHERE YEAR(payment_date) = p_ano;

    START TRANSACTION;
    DELETE FROM receita_mes WHERE ano = p_ano;
    INSERT INTO receita_mes (ano, mes, locacoes, receita)
    SELECT p_ano, mes, COUNT(DISTINCT rental_id), SUM(amount)
      FROM stg_pagamentos GROUP BY mes;
    SET v_linhas = ROW_COUNT();
    IF v_linhas = 0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Ano sem pagamentos';
    END IF;
    INSERT INTO etl_log (ano, linhas, situacao, executado_em) VALUES (p_ano, v_linhas, 'OK', NOW());
    COMMIT;
END $$
DELIMITER ;

CALL sp_etl_receita_mes(2005);
CALL sp_etl_receita_mes(2005);   -- não duplica
CALL sp_etl_receita_mes(2010);   -- erro

SELECT mes, receita, DENSE_RANK() OVER (ORDER BY receita DESC) AS posicao
  FROM receita_mes WHERE ano = 2005;
```

Resultado: 4 meses (5 a 8). Julho maior receita (28373.89).
