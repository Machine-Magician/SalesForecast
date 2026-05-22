package com.barcodescanner

import android.graphics.Rect

class BarcodeMemory {
    private val codes = mutableMapOf<String, BarcodeData>()

    fun add(text: String, rect: Rect, confidence: Float): Boolean {
        val last = codes[text]
        if (last != null && System.currentTimeMillis() - last.timestamp < 2000) {
            return false  // дубликат за 2 секунды
        }
        codes[text] = BarcodeData(text, rect, confidence, System.currentTimeMillis())
        return true
    }

    fun getAll(): List<BarcodeData> = codes.values.toList()
    fun size() = codes.size
    fun clear() = codes.clear()
}

data class BarcodeData(
    val text: String,
    val rect: Rect,
    val confidence: Float,
    val timestamp: Long
)