package com.barcodescanner

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Rect
import android.util.AttributeSet
import android.view.View

class OverlayView(context: Context, attrs: AttributeSet?) : View(context, attrs) {

    var hasDetection = false

    private val readBoxes = mutableListOf<Triple<String, Rect, Long>>()

    private val greenPaint = Paint().apply {
        style = Paint.Style.STROKE
        strokeWidth = 6f
        color = Color.rgb(0, 200, 200)
    }

    private val greenBg = Paint().apply {
        style = Paint.Style.FILL
        color = Color.rgb(0, 150, 150)
    }

    private val textPaint = Paint().apply {
        color = Color.WHITE
        textSize = 40f
        isFakeBoldText = true
    }

    private val circlePaint = Paint().apply {
        style = Paint.Style.FILL
    }

    fun addReadBox(text: String, rect: Rect) {
        readBoxes.add(Triple(text, rect, System.currentTimeMillis()))
        invalidate()
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        val now = System.currentTimeMillis()

        // Светофор
        circlePaint.color = if (hasDetection) Color.GREEN else Color.BLUE
        canvas.drawCircle(60f, 60f, 40f, circlePaint)

        // Бирюзовые рамки с текстом (2 секунды)
        val toRemove = mutableListOf<Triple<String, Rect, Long>>()
        for ((text, rect, ts) in readBoxes) {
            if (now - ts > 2000) {
                toRemove.add(Triple(text, rect, ts))
                continue
            }
            canvas.drawRect(rect.left.toFloat(), rect.top.toFloat(),
                rect.right.toFloat(), rect.bottom.toFloat(), greenPaint)

            val tw = textPaint.measureText(text)
            canvas.drawRect(rect.left.toFloat(), rect.top.toFloat() - 45,
                rect.left + tw + 8, rect.top.toFloat(), greenBg)
            canvas.drawText(text, rect.left + 4f, rect.top.toFloat() - 8, textPaint)
        }
        readBoxes.removeAll(toRemove)

        postInvalidateDelayed(50)
    }
}