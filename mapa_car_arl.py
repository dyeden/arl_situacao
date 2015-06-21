import arcpy
from os import path, mkdir
from shutil import rmtree
from sys import argv

projecao_geo ='GEOGCS["GCS_SIRGAS_2000",DATUM["D_SIRGAS_2000",' \
              'SPHEROID["GRS_1980",6378137.0,298.257222101]],' \
              'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]]'
projecao_plana ='PROJCS["SIRGAS_2000_Lambert_Conformal_Conic_PA",' \
                'GEOGCS["GCS_SIRGAS_2000",DATUM["D_SIRGAS_2000",SPHEROID' \
                '["GRS_1980",6378137.0,298.257222101]],PRIMEM["Greenwich",0.0]' \
                ',UNIT["Degree",0.0174532925199433]],PROJECTION' \
                '["Lambert_Conformal_Conic"],PARAMETER["False_Easting",0.0],PARAMETER' \
                '["False_Northing",0.0],PARAMETER["Central_Meridian",-52.5],PARAMETER' \
                '["Standard_Parallel_1",-0.5],' \
                'PARAMETER["Standard_Parallel_2",-6.833333333333333]' \
                ',PARAMETER["Latitude_Of_Origin",-3.666667],UNIT["Meter",1.0]]'

def create_layers():
    arcpy.MakeFeatureLayer_management("ENTRADA/CAR_1507953.shp", "CAR")
    arcpy.MakeFeatureLayer_management("ENTRADA/DESMATAMENTO_PRODES_1507953.shp",
                                      "PRODES", "ano IN ( '2012' , '2013' , '2014' )")
    arcpy.MakeFeatureLayer_management("ENTRADA/MUNICIPIO_1507953.shp", "MUNICIPIO")
    arcpy.MakeFeatureLayer_management("ENTRADA/TERRACLASS_2008_1507953.shp", "TC_2008")
    arcpy.MakeFeatureLayer_management("ENTRADA/TERRACLASS_2012_1507953.shp", "TC_2012")

def area_floresta_2008(poly_car):
    arcpy.SelectLayerByLocation_management(
        "TC_2008","INTERSECT",poly_car,"","NEW_SELECTION")
    desc = arcpy.Describe("TC_2008")
    area_floresta = 0
    if len(desc.FIDSet) > 0:
        for row in arcpy.da.SearchCursor("TC_2008",["OID@", "SHAPE@"],
                                         "tcclasse = '  FLORESTA'"):
            poly_inter_flo = poly_car.intersect(row[1],4)
            area_floresta += poly_inter_flo.projectAs(projecao_plana).area
    return area_floresta

def area_vegetacao_2014(poly_car):
    area_floresta = 0
    poly_flo_2012 = None
    poly_veg_2014 = None
    arcpy.SelectLayerByLocation_management(
        "TC_2012","INTERSECT",poly_car,"","NEW_SELECTION")
    desc = arcpy.Describe("TC_2012")
    if len(desc.FIDSet) > 0:
        for row in arcpy.da.SearchCursor("TC_2012",["OID@", "SHAPE@"],
                                         "tc_2012 IN ('FLORESTA', 'VEGETACAO_SECUNDARIA')"):
            if poly_flo_2012:
                poly_flo_2012 = poly_car.intersect(row[1],4).union(poly_flo_2012)
            else:
                poly_flo_2012 = poly_car.intersect(row[1],4)
    if poly_flo_2012:
        poly_prodes = None
        arcpy.SelectLayerByLocation_management(
            "PRODES","INTERSECT",poly_car,"","NEW_SELECTION")
        desc = arcpy.Describe("PRODES")
        if len(desc.FIDSet) > 0:
            for row in arcpy.da.SearchCursor("PRODES",["OID@", "SHAPE@"]):
                if poly_prodes:
                    poly_prodes = poly_car.intersect(row[1],4).union(poly_prodes)
                else:
                    poly_prodes = poly_car.intersect(row[1],4)
            if poly_prodes:
                poly_veg_2014 = poly_flo_2012.difference(poly_prodes)
            else:
                poly_veg_2014 = poly_flo_2012
    if poly_veg_2014:
        area_floresta = poly_veg_2014.projectAs(projecao_plana).area
    return area_floresta

def analisar_situacao(area_arl, area_veg_2014):
    situacao  = None
    if area_arl == 0 or area_veg_2014/area_arl >= 1:
        situacao = "otima"
    elif area_veg_2014/area_arl >= 0.75:
        situacao= "moderada"
    elif area_veg_2014/area_arl >= 0.5:
        situacao= "ruim"
    elif area_veg_2014/area_arl < 0.5:
        situacao= "critica"
    return situacao

def calcular_arl(area_flo_2008, area_car, poly_car, mf_mun):
    area_arl = 0
    if area_car*0.0001 > 4*mf_mun:
        if area_flo_2008/area_car > 0.8:
            area_arl = area_car*0.8
        elif (area_flo_2008/area_car) > 0.5 and (area_flo_2008/area_car) <= 0.8:
            area_arl  = area_flo_2008
        else:
            area_arl = area_car*0.5
    else:
        if area_flo_2008/area_car > 0.8:
            area_arl = area_car*0.8
        else:
            area_arl = area_flo_2008
    return area_arl

def car_evaluation():

    arcpy.CreateFeatureclass_management("SAIDA",
                                        "CAR_ANALISADO.shp",
                                        "POLYGON", "", "", "", projecao_geo)
    arcpy.AddField_management("SAIDA/CAR_ANALISADO.shp", "area_car", "FLOAT")
    arcpy.AddField_management("SAIDA/CAR_ANALISADO.shp", "area_arl", "FLOAT")
    arcpy.AddField_management("SAIDA/CAR_ANALISADO.shp", "porc_arl", "FLOAT")
    arcpy.AddField_management("SAIDA/CAR_ANALISADO.shp", "area_flo08", "FLOAT")
    arcpy.AddField_management("SAIDA/CAR_ANALISADO.shp", "porc_flo08", "FLOAT")
    arcpy.AddField_management("SAIDA/CAR_ANALISADO.shp", "area_flo", "FLOAT")
    arcpy.AddField_management("SAIDA/CAR_ANALISADO.shp", "porc_flo", "FLOAT")
    arcpy.AddField_management("SAIDA/CAR_ANALISADO.shp", "mf", "FLOAT")
    arcpy.AddField_management("SAIDA/CAR_ANALISADO.shp", "situacao", "TEXT")
    cursor_insert = arcpy.da.InsertCursor("SAIDA/CAR_ANALISADO.shp",
                                          ['Id', 'SHAPE@', "area_car", "area_arl","porc_arl",
                                          "area_flo08", "porc_flo08","area_flo", "porc_flo",
                                          "mf", "situacao"])
    municipio_geo = None
    mf_mun = 50
    for row in arcpy.da.SearchCursor("MUNICIPIO",["SHAPE@"]):
        municipio_geo = row[0]

    for row in arcpy.da.SearchCursor("CAR",["OID@", "SHAPE@"]):
        print row[0]
        area_car = row[1].projectAs(projecao_plana).area
        poly_car = row[1]
        car_ok = False
        if municipio_geo.contains(poly_car):
            car_ok = True
        else:
            poly_inter_mun = municipio_geo.intersect(poly_car, 4)
            area_inter_mun = poly_inter_mun.projectAs(projecao_plana).area
            if area_inter_mun/area_car > 0.4:
                car_ok = True
        if car_ok:
            area_flo_2008 = area_floresta_2008(poly_car)
            porc_flo_2008 = (area_flo_2008/area_car)*100
            area_flo_2014 = area_vegetacao_2014(poly_car)
            porc_flo_2014 = (area_flo_2014/area_car)*100
            area_arl = calcular_arl(area_flo_2008, area_car, poly_car, mf_mun)
            porc_arl = (area_arl/area_car)*100
            situacao = analisar_situacao(area_arl, area_flo_2014)
            mf_car = round(area_car/mf_mun, 2)

            cursor_insert.insertRow((row[0],poly_car,area_car, area_arl, porc_arl,
                                     area_flo_2008, porc_flo_2008,area_flo_2014,
                                     porc_flo_2014, mf_car, situacao))
    del cursor_insert

def main():
    diretorio_saida = "SAIDA"
    if path.exists(diretorio_saida):
        rmtree(diretorio_saida)
    mkdir(diretorio_saida)
    create_layers()
    car_evaluation()
if __name__ == '__main__':
    main()