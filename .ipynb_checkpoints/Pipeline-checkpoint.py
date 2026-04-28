import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime

# =========================
# 1. Ingestão de Dados
# =========================
def carregar_dados(base_path, dim_path):
    """
    Carrega os arquivos parquet da base de disparos e da dimensão de telefones.
    Explode o campo de aparições e normaliza para formar um dataframe consolidado.
    """
    base = pd.read_parquet(base_path)
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
    """
    Cria um índice de confiabilidade por sistema combinando:
    - Taxa de entrega em números válidos (peso positivo máximo)
    - Taxa de entrega em suspeitos (peso moderado)
    - Taxa de entrega em inválidos (peso negativo)
    """
    mapa_qualidade = {"INVALIDO":"BAIXA","SUSPEITO":"MEDIA","VALIDO":"ALTA"}
    df["telefone_qualidade_cat"] = df["telefone_qualidade"].map(mapa_qualidade)

    resumo = (
        df.groupby(["id_sistema","telefone_qualidade_cat"])
          .agg(total=("status_disparo","count"),
               entregues=("status_disparo", lambda x: (x=="DELIVERED").sum()))
          .reset_index()
    )
    resumo["taxa_entrega"] = resumo["entregues"]/resumo["total"]

    pivot = resumo.pivot(index="id_sistema", columns="telefone_qualidade_cat", values="taxa_entrega").fillna(0)
    pivot["indice_confiabilidade"] = (pivot.get("ALTA",0)*1.0) + (pivot.get("MEDIA",0)*0.5) - (pivot.get("BAIXA",0)*0.5)
    return pivot.sort_values("indice_confiabilidade", ascending=False)

# =========================
# 3. Algoritmo de Seleção por CPF
# =========================
def calcular_score(origem, data_atualizacao, ddd, ddd_ref):
    """
    Calcula score de confiabilidade de um telefone:
    - Origem do dado (OFICIAL, SECUNDARIA, EXTERNA)
    - Recência da atualização
    - Compatibilidade do DDD com a região do CPF
    """
    pesos_origem = {"OFICIAL":50,"SECUNDARIA":30,"EXTERNA":10}
    score_origem = pesos_origem.get(str(origem).upper(),0)

    try:
        dias = (datetime.today()-pd.to_datetime(data_atualizacao)).days
    except:
        dias = 9999
    score_tempo = max(0,40-dias/30)

    try:
        if str(ddd)==str(ddd_ref):
            score_ddd=20
        elif abs(int(ddd)-int(ddd_ref))<=1:
            score_ddd=10
        else:
            score_ddd=0
    except:
        score_ddd=0

    return score_origem+score_tempo+score_ddd

def selecionar_melhores_por_cpf(df, n=2):
    """
    Seleciona automaticamente os n melhores telefones por CPF usando o score.
    """
    resultados={}
    cpfs=df["cpf_y"].dropna().unique()
    for cpf in cpfs:
        subset=df[df["cpf_y"]==cpf].copy()
        if subset.empty: continue
        ddd_ref=subset["telefone_ddd"].mode()[0] if not subset["telefone_ddd"].dropna().empty else None
        subset["score"]=subset.apply(lambda row: calcular_score(
            origem=row.get("validacao_telefone","EXTERNA"),
            data_atualizacao=row.get("registro_data_atualizacao",datetime.today()),
            ddd=row.get("telefone_ddd",0),
            ddd_ref=ddd_ref),axis=1)
        ranking=subset.sort_values("score",ascending=False)
        resultados[cpf]=ranking[["contato_telefone","telefone_ddd","validacao_telefone","registro_data_atualizacao","score"]].head(n)
    return resultados

# =========================
# 4. Gráfico de Decaimento da Qualidade
# =========================
def grafico_decaimento(df):
    """
    Gera gráfico mostrando o decaimento da qualidade do dado ao longo do tempo.
    - Calcula idade do telefone em anos a partir da data de atualização.
    - Agrupa em faixas de idade.
    - Mostra taxa de entrega por faixa.
    """
    df["idade_anos"] = (datetime.today() - pd.to_datetime(df["registro_data_atualizacao"], errors="coerce")).dt.days / 365

    bins = [0, 5, 10, 15, 20, 30]
    labels = ["0-5 anos", "6-10 anos", "11-15 anos", "16-20 anos", "21-30 anos"]
    df["faixa_idade"] = pd.cut(df["idade_anos"], bins=bins, labels=labels, include_lowest=True)

    resumo = (
        df.groupby("faixa_idade")
          .agg(total=("status_disparo","count"),
               entregues=("status_disparo", lambda x: (x=="DELIVERED").sum()))
          .reset_index()
    )
    resumo["taxa_entrega"] = resumo["entregues"]/resumo["total"]

    plt.figure(figsize=(10,6))
    plt.plot(resumo["faixa_idade"], resumo["taxa_entrega"], marker="o", color="darkred")
    plt.title("Decaimento da Qualidade do Dado ao Longo do Tempo")
    plt.xlabel("Faixa de Idade do Telefone")
    plt.ylabel("Taxa de Entrega")
    plt.grid(True)
    plt.tight_layout()
    plt.show()

    return resumo

# =========================
# 5. Execução da Pipeline
# =========================
if __name__=="__main__":
    df=carregar_dados(r"C:\Users\Bruno\Downloads\whatsapp_base_disparo_mascarado",
                      r"C:\Users\Bruno\Downloads\whatsapp_dim_telefone_mascarado")

    print("\n=== Ranking de Sistemas ===")
    print(ranking_sistemas(df).head(10))

    print("\n=== Seleção dos 2 melhores telefones por CPF ===")
    melhores=selecionar_melhores_por_cpf(df,n=2)
    for cpf, top in list(melhores.items())[:3]:  # mostra só os 3 primeiros CPFs
        print(f"\nCPF: {cpf}")
        print(top)

    print("\n=== Análise de Decaimento da Qualidade ===")
    resumo_decaimento = grafico_decaimento(df)
    print(resumo_decaimento)
