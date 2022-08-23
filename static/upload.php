<?php
$cod_mun=$_POST["cod_mun"];
$target_dir = "results/".$cod_mun."/";
$target_file = $target_dir . basename($_FILES["fileToUpload"]["name"]);
$uploadOk = 1;
$fileName = strtolower(pathinfo($target_file,PATHINFO_FILENAME));
$fileType = strtolower(pathinfo($target_file,PATHINFO_EXTENSION));

// check cod_mun, it should be 5 digits
$pattern = "/^\d\d\d\d\d/";
if ( !preg_match($pattern, $cod_mun)) {
    exit;
}

// Check file size
//if ($_FILES["fileToUpload"]["size"] > 500000) {
//  echo "ERROR: este archivo es demasiado pesado.";
//  $uploadOk = 0;
//}

// Allow certain file formats
if($fileType != "csv" ) {
  echo "ERROR: debería ser un archivo csv.";
  $uploadOk = 0;
}

if($fileName != "highway_names") {
  echo "ERROR: deberías subir el archivo highway_names.csv revisado manualmente.";
  $uploadOk = 0;
}

// Check if $uploadOk is set to 0 by an error
if ($uploadOk == 0) {
  echo "<br>Algo falló :(";
// if everything is ok, try to upload file
} else {
  if (move_uploaded_file($_FILES["fileToUpload"]["tmp_name"], $target_file)) {
    echo "El archivo <a href=https://cat.cartobase.es/results/".$cod_mun."/highway_names.csv>highway_names.csv</a> se ha subido correctamente.<br> Ahora deberías de volver a lanzar el paso 1. (Procesar edificios)";
  } else {
    echo "Lo siento, algo falló subiendo tu archivo.";
  }
}

    echo '<br><br><a href="javascript:history.back()">Volver</a>';
?>
