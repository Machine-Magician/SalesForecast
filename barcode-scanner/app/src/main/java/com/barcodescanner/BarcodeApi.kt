package com.barcodescanner

import com.google.gson.GsonBuilder
import java.net.HttpURLConnection
import java.net.URL

object BarcodeApi {
    fun toJson(barcodes: List<BarcodeData>): String {
        val gson = GsonBuilder().setPrettyPrinting().create()
        val data = mapOf(
            "timestamp" to System.currentTimeMillis(),
            "total" to barcodes.size,
            "barcodes" to barcodes.map {
                mapOf(
                    "text" to it.text,
                    "confidence" to it.confidence,
                    "bbox" to listOf(it.rect.left, it.rect.top, it.rect.right, it.rect.bottom)
                )
            }
        )
        return gson.toJson(data)
    }

    fun send(json: String, callback: (Boolean) -> Unit) {
        Thread {
            try {
                val url = URL("https://your-api.com/barcodes")
                val conn = url.openConnection() as HttpURLConnection
                conn.requestMethod = "POST"
                conn.setRequestProperty("Content-Type", "application/json")
                conn.doOutput = true
                conn.outputStream.write(json.toByteArray())
                callback(conn.responseCode == 200)
            } catch (e: Exception) {
                callback(false)
            }
        }.start()
    }
}