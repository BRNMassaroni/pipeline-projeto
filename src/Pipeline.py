import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
import pyarrow.parquet as pq

# =========================
# 1. Ingestão de Dados (Otimizada)
# =========================
def carregar_dados_limitados(base_path, dim_path, limit=10000):
    table = pq.read_table(base_path)
    base = table.slice(0, limit).to_pandas()
    dim = pd.read_parquet(dim_path)

    base["contato_telefone"] = base["contato_telefone"].astype(str)
    
    dim_explodido = dim.explode("telefone_aparicoes").reset_index(drop=True)
    aparicoes_expandido = pd.json_normalize(dim_explodido["telefone_aparicoes"])
    dim_expandido = pd.concat([dim_explodido.drop(columns=["telefone_aparicoes"]), aparicoes_expandido], axis=1)
    dim_expandido["telefone_numero"] = dim_expandido["telefone_numero"].astype(str)

    df = base.merge(dim_expandido, left_on="contato_telefone", right_on="telefone_numero")
    df["status_disparo"] = df["status_disparo"].fillna("").astype(str).str.strip().str.upper()
    return df

# =========================
# 2. Ranking de Sistemas
# =========================
def ranking_sistemas(df):
    mapa_qualidade = {"INVALIDO": "BAIXA", "SUSPEITO": "MEDIA", "VALIDO": "ALTA"}
    df["telefone_qualidade_cat"] = df["telefone_qualidade"].map(mapa_qualidade)

    resumo = (
        df.groupby(["id_sistema", "telefone_qualidade_cat"])
          .agg(total=("status_disparo", "count"),
               entregues=("status_disparo", lambda x: (x == "DELIVERED").sum()))
          .reset_index()
    )
    resumo["taxa_entrega"] = resumo["entregues"] / resumo["total"]

    pivot = resumo.pivot(index="id_sistema", columns="telefone_qualidade_cat", values="taxa_entrega").fillna(0)
    pivot["indice_confiabilidade"] = (pivot.get("ALTA", 0) * 1.0) + (pivot.get("MEDIA", 0) * 0.5) - (pivot.get("BAIXA", 0) * 0.5)
    return pivot.sort_values("indice_confiabilidade", ascending=False)

# =========================
# 3. Algoritmo de Seleção por CPF (Vetorizado)
# =========================
def selecionar_melhores_por_cpf(df, n=2):
    modes = df.groupby("cpf_y")["telefone_ddd"].agg(lambda x: x.mode().iloc[0] if not x.mode().empty else None)
    df = df.merge(modes.rename("ddd_ref"), on="cpf_y", how="left")

    pesos_origem = {"OFICIAL": 50, "SECUNDARIA": 30, "EXTERNA": 10}
    df["score_origem"] = df["validacao_telefone"].astype(str).str.upper().map(pesos_origem).fillna(0)

    dias = (datetime.today() - pd.to_datetime(df["registro_data_atualizacao"], errors="coerce")).dt.days.fillna(9999)
    df["score_tempo"] = (40 - dias / 30).clip(lower=0)

    df["score_ddd"] = 0
    mask_igual = df["telefone_ddd"].astype(str) == df["ddd_ref"].astype(str)
    
    ddd_numeric = pd.to_numeric(df["telefone_ddd"], errors='coerce')
    ref_numeric = pd.to_numeric(df["ddd_ref"], errors='coerce')
    distancia_ddd = (ddd_numeric - ref_numeric).abs()
    
    df.loc[mask_igual, "score_ddd"] = 20
    df.loc[(~mask_igual) & (distancia_ddd <= 1), "score_ddd"] = 10

    df["score"] = df["score_origem"] + df["score_tempo"] + df["score_ddd"]

    return df.sort_values(by="score", ascending=False).groupby("cpf_y").head(n)

# =========================
# 4. Gráfico de Decaimento (Agora focado em Qualidade)
# =========================
def grafico_decaimento(df):
    # Mapeamento da Qualidade
    mapa_qualidade = {"INVALIDO": "BAIXA", "SUSPEITO": "MEDIA", "VALIDO": "ALTA"}
    df["telefone_qualidade_cat"] = df["telefone_qualidade"].map(mapa_qualidade)

    # Cálculo da Idade
    df["idade_anos"] = (datetime.today() - pd.to_datetime(df["registro_data_atualizacao"], errors="coerce")).dt.days / 365
    bins = [0, 5, 10, 15, 20, 30]
    labels = ["0-5 anos", "6-10 anos", "11-15 anos", "16-20 anos", "21-30 anos"]
    df["faixa_idade"] = pd.cut(df["idade_anos"], bins=bins, labels=labels, include_lowest=True)

    # Agrupamento: Contagem de cada qualidade por faixa etária
    resumo = df.groupby(["faixa_idade", "telefone_qualidade_cat"]).size().unstack(fill_value=0)
    
    # Normalização para gerar o gráfico de distribuição (em %)
    resumo_pct = resumo.div(resumo.sum(axis=1), axis=0) * 100

    # Plotagem: Barra empilhada (Stacked Bar)
    # Definindo cores padrão para consistência visual
    cores = {'ALTA': '#2ca02c', 'MEDIA': '#ff7f0e', 'BAIXA': '#d62728'}
    
    ax = resumo_pct.plot(kind='bar', stacked=True, figsize=(10, 6), color=[cores.get(x, 'grey') for x in resumo_pct.columns])
    
    plt.title("Distribuição da Qualidade dos Telefones por Faixa Etária")
    plt.xlabel("Faixa de Idade do Telefone")
    plt.ylabel("Distribuição (%)")
    plt.legend(title="Qualidade", loc='upper right')
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.tight_layout()

    plt.savefig("grafico_qualidade_idade.png")
    plt.close() 
    print("Gráfico de qualidade salvo como 'grafico_qualidade_idade.png'")
    return resumo_pct

# =========================
# 5. Execução
# =========================
if __name__ == "__main__":
    df = carregar_dados_limitados(r"C:\Users\Bruno\Downloads\whatsapp_base_disparo_mascarado",
                                  r"C:\Users\Bruno\Downloads\whatsapp_dim_telefone_mascarado",
                                  limit=10000)

    print(f"\nBase carregada com {len(df)} registros.")

    print("\n=== Ranking de Sistemas ===")
    print(ranking_sistemas(df).head(10))

    # Filtro para os 3 primeiros CPFs que possuem > 3 contatos
    contagem_por_cpf = df.groupby("cpf_y").size()
    cpfs_alvo = contagem_por_cpf[contagem_por_cpf > 3].index[:3]
    df_subset = df[df["cpf_y"].isin(cpfs_alvo)].copy()

    print(f"\n=== Seleção dos 2 melhores telefones (Subset CPFs) ===")
    if not df_subset.empty:
        melhores = selecionar_melhores_por_cpf(df_subset, n=2)
        for cpf, group in melhores.groupby("cpf_y"):
            print(f"\nCPF: {cpf} (Total: {contagem_por_cpf[cpf]})")
            print(group[["contato_telefone", "telefone_ddd", "validacao_telefone", "score"]])
    
    print("\n=== Análise de Decaimento da Qualidade ===")
    resumo_decaimento = grafico_decaimento(df)
    print(resumo_decaimento)