; Batch GIMP: convert one file to PNG or DDS (requires GIMP DDS plugin for .dds).
; Usage (gimp-console):
;   gimp-console -i -b "(lbg-dds-convert \"in.dds\" \"out.png\" 'png)" -b "(gimp-quit 0)"
;   gimp-console -i -b "(lbg-dds-convert \"in.png\" \"out.dds\" 'dds)" -b "(gimp-quit 0)"

(define (lbg-dds-convert in-path out-path fmt)
  (let* ((run-mode 1)
         (image (car (gimp-file-load run-mode in-path in-path)))
         (drawable (car (gimp-image-get-active-layer image))))
    (cond
      ((equal? fmt 'png)
       (file-png-save run-mode image drawable out-path out-path 0 9 0 0 0 0 0))
      ((equal? fmt 'dds)
       (file-dds-save run-mode image drawable out-path out-path))
      (else (error "fmt doit etre png ou dds")))
    (gimp-image-delete image)))
