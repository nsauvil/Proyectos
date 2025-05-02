# encoding: utf-8

from pyspark.sql.functions import *
from pyspark.sql.types import *
from pyspark.sql.window import Window
from pyspark.sql import SparkSession

spark = SparkSession.builder.appName('Spark_IMF_Big_Data').getOrCreate()

#---------------------------------------------------------------------------------------------------------------------
# CASO 1

df_facturas_mes_ant = spark.read.table("sector_telecomunicaciones.df_facturas_mes_ant")

# Agrupamos por el id_cliente y sumamos las ofertas que tiene cada uno.
# La suma se almacena en una nueva columna (num_contratos).
df_modificado = df_facturas_mes_ant.groupBy("id_cliente").agg(count("id_oferta").alias("num_contratos"))

# Se filtra por los clientes con más de un contrato.
# Una vez filtrado, se cuenta el número de clientes.
n_clientes_mas_de_un_contrato =df_modificado.filter(df_modificado["num_contratos"] > 1).count()

print("El numero total de clientes del mes anterior con mas de un contrato es de: " + str(n_clientes_mas_de_un_contrato))

#---------------------------------------------------------------------------------------------------------------------
# CASO 2

df_facturas_mes_ant = spark.read.table("sector_telecomunicaciones.df_facturas_mes_ant")
df_facturas_mes_actual = spark.read.table("sector_telecomunicaciones.df_facturas_mes_actual")

# Unimos los df del mes actual y del anterior.
# Aquellos que tengan la columna "mes_ant" a null seran los clientes nuevos.
# Tambien eliminamos los duplicados.
df_facturas_mes_actual_aux = df_facturas_mes_actual.join(df_facturas_mes_ant.select("id_cliente").withColumn("mes_ant", lit(1)), ["id_cliente"], "left") \
.dropDuplicates(["id_cliente","id_oferta","importe"])

# Añadimos la columna con el descuento del 7% (solo sobre las filas con "mes_ant" == 1).
# Ordenamos "id_cliente" ascendente e "importe" descendente
df_facturas_mes_actual = df_facturas_mes_actual_aux.withColumn("importe_dto", when (col("mes_ant") == 1, \
                                                                                    (col("importe")*0.93).cast(DecimalType(17,2))) \
                                                                                    .otherwise(col("importe"))) \
                                                                                    .orderBy(["id_cliente", "importe"], ascending=[1,0]) \
                                                                                    .select(["id_cliente","id_oferta","importe","fecha","importe_dto"])

df_facturas_mes_actual.show(n=50)

#---------------------------------------------------------------------------------------------------------------------
# CASO 3

# Suponemos que el df de facturas actuales no es el del ejercicio anterior:       
df_facturas_mes_actual = spark.read.table("sector_telecomunicaciones.df_facturas_mes_actual")
df_ofertas = spark.read.table("sector_telecomunicaciones.df_ofertas")

# Guardamos los id de las ofertas que incluyen datos ilimitados.
# Para distinguirlas al realizar join con las facturas, se añade una columna extra "importe_dto".
ofertas_di = df_ofertas.filter(col("descripcion").contains("datos ilimitados")).select("id_oferta") \
    .withColumn("importe_dto", lit(1))

# Unimos los df e incrementamos el importe de los clientes que contrataron datos ilimitados.
# Para que el df se vea más limpio, el importe se va a castear a dos decimales y el df final se ordenará según el id_cliente y el importe.
df_facturas_mes_actual = df_facturas_mes_actual.join(ofertas_di, ["id_oferta"], "left") \
    .withColumn("importe", when (col("importe_dto") == 1, (col("importe")*1.15).cast(DecimalType(17,2))) \
                .otherwise(col("importe"))).orderBy(["id_cliente", "importe"], ascending=[1,0]) \
                .select(["id_cliente","id_oferta","importe","fecha"])

df_facturas_mes_actual.show(n=50)

#---------------------------------------------------------------------------------------------------------------------
# CASO 4

df_facturas_mes_actual = spark.read.table("sector_telecomunicaciones.df_facturas_mes_actual")
df_facturas_mes_ant = spark.read.table("sector_telecomunicaciones.df_facturas_mes_ant")
df_clientes = spark.read.table("sector_telecomunicaciones.df_clientes")
df_consumos_diarios = spark.read.table("sector_telecomunicaciones.df_consumos_diarios")

# CREAR VARIABLE 'GRUPO_EDAD' PARA LOS DF MES_ANT Y MES_ACTUAL:

# Añadimos la edad de los clientes a los df (la edad está en el df clientes).
df_facturas_mes_ant = df_facturas_mes_ant.join(df_clientes.select("id_cliente", "edad"), ["id_cliente"],"left")
df_facturas_mes_actual = df_facturas_mes_actual.join(df_clientes.select("id_cliente", "edad"), ["id_cliente"],"left")

# Obtenemos los grupos de edad para ambos df.
# NOTA: le cambio el nombre al df por si necesitamos usar los grupos de edad en otros apartados.
df_facturas_mes_ant_ge = df_facturas_mes_ant.withColumn("grupo_edad", when(col("edad") < 26, lit(1)) \
                                                        .when(col("edad").between(26,40), lit(2)) \
                                                        .when(col("edad").between(41,65), lit(3)) \
                                                        .otherwise(lit(4))).orderBy("grupo_edad","id_cliente")
df_facturas_mes_actual_ge = df_facturas_mes_actual.withColumn("grupo_edad", when(col("edad") < 26, lit(1)) \
                                                        .when(col("edad").between(26,40), lit(2)) \
                                                        .when(col("edad").between(41,65), lit(3)) \
                                                        .otherwise(lit(4))).orderBy("grupo_edad","id_cliente")

df_facturas_mes_ant_ge.show(n=10)
df_facturas_mes_actual_ge.show(n=10)

# OBTENER TABLA RESUMEN:

# Para usar pocas operaciones, calculamos los grupos de edad en el df clientes.
df_clientes_ge = df_clientes.select("id_cliente", "edad").withColumn("grupo_edad", when(col("edad") < 26, lit(1)) \
                                                        .when(col("edad").between(26,40), lit(2)) \
                                                        .when(col("edad").between(41,65), lit(3)) \
                                                        .otherwise(lit(4)))

# Lo unimos con el df de consumos diarios.
df_consumos_diarios_ge = df_consumos_diarios.join(df_clientes_ge, ["id_cliente"], "left")

# Agrupamos por grupo de edad y calculamos la tabla resumen.
df_resumen = df_consumos_diarios_ge.groupBy("grupo_edad").agg( \
    (mean("consumo_datos_MB").cast(DecimalType(17,2))).alias("media_consumo_datos_MB"), \
    (mean("sms_enviados").cast(DecimalType(17,2))).alias("media_sms_enviados"), \
    (mean("minutos_llamadas_movil").cast(DecimalType(17,2))).alias("media_minutos_movil"), \
    (mean("minutos_llamadas_fijo").cast(DecimalType(17,2))).alias("media_minutos_fijo") \
).orderBy("grupo_edad")

df_resumen = df_resumen.select("grupo_edad", "media_consumo_datos_MB", "media_sms_enviados", "media_minutos_movil","media_minutos_fijo")
df_resumen.show(n=10)
#---------------------------------------------------------------------------------------------------------------------
# CASO 5

df_clientes = spark.read.table("sector_telecomunicaciones.df_clientes")
df_consumos_diarios = spark.read.table("sector_telecomunicaciones.df_consumos_diarios")

# Unimos los df para que los id_cliente de "consumos_diarios" tengan el sexo.
df_consumos_diarios = df_consumos_diarios.join(df_clientes.select("id_cliente","sexo"),["id_cliente"], "left")

# Date_format es una función de PySpark que permite extraer el día de la semana mediante una abreviatura de tres letras ("Fri" para el viernes)
df_consumos_diarios = df_consumos_diarios.withColumn("dia_semana", date_format(col("fecha"),"E"))

# Nos quedamos solo con los consumos del fin de semana. 
df_consumos_finde = df_consumos_diarios.filter((col("dia_semana") == "Fri") | \
                                               (col("dia_semana") == "Sat") | \
                                               (col("dia_semana") == "Sun"))

# Calculamos el consumo.
df_resultado = df_consumos_finde.groupBy("sexo").agg( \
                sum("minutos_llamadas_movil").alias("total_mins_movil_finde"), \
                sum("consumo_datos_MB").alias("total_datos_moviles_finde"))

df_resultado = df_resultado.select("sexo", "total_mins_movil_finde", "total_datos_moviles_finde")
df_resultado.show()

#---------------------------------------------------------------------------------------------------------------------
# CASO 6

df_clientes = spark.read.table("sector_telecomunicaciones.df_clientes")

# Para este apartado se reutilizará el df df_consumos_diarios_ge del Caso 4 (contiene los clientes, su edad, consumos y los grupos de edad)
# Filtramos los consumos para quedarnos con los primeros 15 días de agosto:
df_consumos_15_d = df_consumos_diarios_ge.filter(col("fecha") <= "2020-08-15")

# Para calcular el consumo por cliente y grupo de edad, agrupamos los datos:
df_consumos_15_d_gb = df_consumos_15_d.groupBy("grupo_edad","id_cliente").agg( \
                                    sum("consumo_datos_MB").alias("datos_moviles_total_15"))

# Para poder agrupar datos y mantener ese conjunto para realizar varios cálculos, usamos Window.
# En este caso, agrupamos por grupo de edad y ordenamos el consumo de datos de mayor a menor
window_ge_consumo = Window.partitionBy("grupo_edad").orderBy(col("datos_moviles_total_15").desc())

# Añadimos una columna para indicar el cliente con mayor consumo (rank==1).
df_consumos_15_d_ranked = df_consumos_15_d_gb.withColumn("rank", row_number().over(window_ge_consumo))
df_consumos_15_d_1 = df_consumos_15_d_ranked.filter(col("rank") == 1)  #Clientes con rank 1

# Solo falta obtener el máximo de SMS enviados en un día por los clientes con rank 1.
# Comenzamos almacenando los consumos de los clientes con rank 1 (sms, llamadas, etc) en los primeros 15 dias.
df_aux = df_consumos_15_d_1.join(df_consumos_15_d, ["id_cliente","grupo_edad"],"inner")

# Calculamos el max de sms:
max_sms = df_aux.groupBy("grupo_edad", "id_cliente").agg(max("sms_enviados").alias("max_sms_enviados_15"))

# Añadimos el max de sms al df con los clientes de rank 1, así como el nombre y edad de los clientes.
df_final = df_consumos_15_d_1.join(max_sms, ["id_cliente", "grupo_edad"],"inner") \
            .join(df_clientes.select("id_cliente", "nombre", "edad"), ["id_cliente"], "left")

df_final = df_final.select("nombre", "edad", "grupo_edad", "datos_moviles_total_15", "max_sms_enviados_15").orderBy("grupo_edad")
df_final.show()

#---------------------------------------------------------------------------------------------------------------------
# CASO 7

df_facturas_mes_actual = spark.read.table("sector_telecomunicaciones.df_facturas_mes_actual")
df_facturas_mes_ant = spark.read.table("sector_telecomunicaciones.df_facturas_mes_ant")
df_clientes = spark.read.table("sector_telecomunicaciones.df_clientes")
df_consumos_diarios = spark.read.table("sector_telecomunicaciones.df_consumos_diarios")

# Primero, nos quedamos con las facturas de los clientes nuevos.
df_facturas_nuevos_clientes = df_facturas_mes_actual.join(df_facturas_mes_ant, ["id_cliente"],"leftanti")

# Calculamos el importe total de los clientes (sumando el importe de todas las ofertas que tienen)
df_importe_total_nc = df_facturas_nuevos_clientes.select("id_cliente", "importe").groupBy("id_cliente").agg( \
                                                  sum("importe").alias("importe_total_mes_actual"))

# Almacenamos los consumos de los clientes nuevos.
df_consumos_nuevos_clientes = df_consumos_diarios.join(df_importe_total_nc,["id_cliente"],"inner")

# Agrupamos los datos y calculamos total_minutos.
df_final = df_consumos_nuevos_clientes.groupBy("id_cliente").agg( \
                                        (sum("minutos_llamadas_movil") + sum("minutos_llamadas_fijo")) \
                                        .alias("total_minutos"))

# Añadimos la edad y el nombre de los clientes.
df_final = df_final.join(df_clientes.select("id_cliente","nombre","edad"), ["id_cliente"], "left") \
                    .join(df_importe_total_nc, ["id_cliente"], "left") \
                    .select("nombre","edad","importe_total_mes_actual", "total_minutos") \
                    .withColumnRenamed("nombre", "nombre_cliente_nuevo").orderBy("total_minutos")

df_final.show()
#---------------------------------------------------------------------------------------------------------------------
# CASO 8

df_facturas_mes_actual = spark.read.table("sector_telecomunicaciones.df_facturas_mes_actual")
df_facturas_mes_ant = spark.read.table("sector_telecomunicaciones.df_facturas_mes_ant")
df_clientes = spark.read.table("sector_telecomunicaciones.df_clientes")
df_consumos_diarios = spark.read.table("sector_telecomunicaciones.df_consumos_diarios")

# Guardamos los id de los clientes que ya existían el mes anterior y siguen haciéndolo en este.
clientes_existian = df_facturas_mes_actual.dropDuplicates(["id_cliente"]) \
                        .join(df_facturas_mes_ant.dropDuplicates(["id_cliente"]), ["id_cliente"],"inner") \
                        .select("id_cliente")

# Obtenemos los consumos de esos clientes y calculamos n_dias_sin_sms
df_aux = df_consumos_diarios.join(clientes_existian, ["id_cliente"],"inner").groupBy("id_cliente") \
                            .agg(count(when(col("sms_enviados") == 0, 1)).alias("n_dias_sin_sms"))

# Añadimos la edad y nombre de los clientes.
df_final = df_aux.join(df_clientes.select("id_cliente", "nombre", "edad"), ["id_cliente"], "left") \
                 .select("nombre", "edad", "n_dias_sin_sms") \
                 .orderBy("edad")

df_final.show(n=30)
#---------------------------------------------------------------------------------------------------------------------
# CASO 9                                                                                                                                              

df_facturas_mes_actual = spark.read.table("sector_telecomunicaciones.df_facturas_mes_actual")
df_clientes = spark.read.table("sector_telecomunicaciones.df_clientes")
df_consumos_diarios = spark.read.table("sector_telecomunicaciones.df_consumos_diarios")

# Los clientes que analizaremos en este apartado son los que tienen solo una oferta contratada en el mes de agosto:
df_facturas_mes_actual = df_facturas_mes_actual.groupBy("id_cliente").agg(count("id_oferta").alias("num_contratos"))
clientes_un_contrato = df_facturas_mes_actual.filter(df_facturas_mes_actual["num_contratos"] == 1).select("id_cliente")

# 1. Sumar todos los días de cada uno de los cuatro consumos para cada cliente.
df_consumos_diarios = df_consumos_diarios.join(clientes_un_contrato, ["id_cliente"], "inner")
df_consumos_diarios = df_consumos_diarios.groupBy("id_cliente").agg( \
                                        sum("consumo_datos_MB").alias("consumo_datos_suma"), \
                                        sum("sms_enviados").alias("sms_enviados_suma"), \
                                        sum("minutos_llamadas_movil").alias("minutos_movil_suma"), \
                                        sum("minutos_llamadas_fijo").alias("minutos_fijo_suma"))

# 2. Obtenemos el máximo de cada consumo.
max_consumo = df_consumos_diarios.agg( \
    max("consumo_datos_suma").alias("max_datos"), \
    max("sms_enviados_suma").alias("max_sms"), \
    max("minutos_movil_suma").alias("max_movil"), \
    max("minutos_fijo_suma").alias("max_fijo")).collect()[0]

# 2.1. Calculamos un valor entre 0-1 para cada consumo.
df_consumos_diarios = df_consumos_diarios \
    .withColumn("datos_moviles_0_1", col("consumo_datos_suma") / max_consumo["max_datos"]) \
    .withColumn("sms_enviados_0_1", col("sms_enviados_suma") / max_consumo["max_sms"]) \
    .withColumn("llamadas_movil_0_1", col("minutos_movil_suma") / max_consumo["max_movil"]) \
    .withColumn("llamadas_fijo_0_1", col("minutos_fijo_suma") / max_consumo["max_fijo"])

# 3. Multiplicar las columnas nuevas por su ponderación correspondiente.
df_consumos_diarios = df_consumos_diarios.withColumn("datos_moviles_0_1", col("datos_moviles_0_1")*0.3) \
                       .withColumn("sms_enviados_0_1", col("sms_enviados_0_1")*0.1) \
                       .withColumn("llamadas_movil_0_1", col("llamadas_movil_0_1")*0.4) \
                       .withColumn("llamadas_fijo_0_1", col("llamadas_fijo_0_1")*0.2)

# 4. Sumar las ponderaciones de cada cliente, casteando a tres decimales.
df_consumos_diarios = df_consumos_diarios.withColumn("coeficiente_cliente", \
                        (col("datos_moviles_0_1") + col("sms_enviados_0_1") + col("llamadas_movil_0_1") + col("llamadas_fijo_0_1")) \
                            .cast(DecimalType(17,3)))

# Añadir la edad y el nombre de los clientes:
df_consumos_diarios = df_consumos_diarios.join(df_clientes.select("id_cliente", "nombre", "edad"), ["id_cliente"], "inner")

# 5. Ordenar el df por el coeficiente en desc
df_consumos_diarios = df_consumos_diarios.orderBy("coeficiente_cliente", ascending=[0]) \
                        .select("nombre", "edad", "coeficiente_cliente") 

df_consumos_diarios.show()
#---------------------------------------------------------------------------------------------------------------------
# CASO 10

df_consumos_diarios = spark.read.table("sector_telecomunicaciones.df_consumos_diarios")

# Primero, obtener los tres clientes que más datos consumen de cada "grupo edad".
# Como se hace referencia al consumo, suponemos que los clientes son del mes de agosto. 
# Pero como no se especifica que los clientes deban tener solo una oferta, no se reutilizarán los datos del caso anterior.
# Reutilizamos el df del Caso 4 (ya tiene los grupos de edad para los clientes del mes actual)
clientes_ge = df_facturas_mes_actual_ge.dropDuplicates(["id_cliente"]).select("id_cliente", "grupo_edad")

# Obtenemos los datos de consumo y calculamos la suma por grupo de edad y cliente.
df_aux = df_consumos_diarios.join(clientes_ge, ["id_cliente"], "inner")
df_aux = df_aux.groupBy("grupo_edad", "id_cliente").agg( \
                                        sum("consumo_datos_MB").alias("consumo_datos_suma"))

# Separamos a los tres clientes con mayor consumo:
window_cli_3 = Window.partitionBy("grupo_edad").orderBy(col("consumo_datos_suma").desc())
df_ranked = df_aux.withColumn("rank", row_number().over(window_cli_3))
df_top3 = df_ranked.filter(col("rank") <= 3).orderBy("rank")

# Una vez obtenidos los clientes con mayor consumo de datos, almacenamos sus datos.
df_consumos_top3 = df_consumos_diarios.join(df_top3.select("id_cliente","grupo_edad"), ["id_cliente"], "inner")

# Creamos otra ventana para organizar los consumos en función del grupo de edad y la fecha.
# Al poner "unbounded" y "current" como parámetros, se obtiene la suma acumulada. 
# Con "unbounded" y "unbounded", por ejemplo, se obtendría la misma suma en todas las filas.
window_fechas = Window.partitionBy("grupo_edad").orderBy("fecha").rowsBetween(Window.unboundedPreceding, Window.currentRow)
df_top3_acumulado = df_consumos_top3.withColumn("consumo_acumulado_MB", sum("consumo_datos_MB").over(window_fechas))

# Buscamos la fecha en la que se alcanzan los 20 GB (20480 MB).
df_final_aux = df_top3_acumulado.filter(col("consumo_acumulado_MB") >= 20480) \
                       .groupBy("grupo_edad") \
                       .agg(min("fecha").alias("fecha_20_GB"))  #La primera fecha (si la hay) en la que se obtienen los 20GB

# Obtenemos la suma del consumo de los tres clientes de cada grupo y lo unimos con el df anterior.
df_final = df_top3.groupBy("grupo_edad").agg(sum("consumo_datos_suma").alias("datos_moviles_total_grupo_3_clientes")) \
                    .join(df_final_aux, ["grupo_edad"], "left") 

# Ordenamos los datos por el grupo edad.
df_final = df_final.select("grupo_edad", "fecha_20_GB", "datos_moviles_total_grupo_3_clientes").orderBy("grupo_edad")
df_final.show()
#---------------------------------------------------------------------------------------------------------------------