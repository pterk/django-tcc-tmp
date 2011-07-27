// closure
(function($) {

    // private vars (within the closure)
    var opts;

    //
    // plugin definition
    //
    $.fn.tcc = function(options){
        // build main options before element iteration
        opts = $.extend({}, $.fn.tcc.defaults, options);
        // iterate and reformat each matched element
        return this.each(function(){
            init();
        });
    };
                        
    // Default width and height for the editor
    $.fn.tcc.defaults = {
        user_id: null,
        user_name: null,
    };

    //
    // private function for debugging
    //
    function debug(msg) {
        if(window.console && window.console.log){
            window.console.log(msg);
        }
    };

    function isScrolledIntoView(elem){
      var docViewTop = $(window).scrollTop();
      var docViewBottom = docViewTop + $(window).height();
      var elemTop = $(elem).offset().top;
      var elemBottom = elemTop + $(elem).height();
      return ((elemBottom >= docViewTop) && (elemTop <= docViewBottom));
    }

    function init(){
        $('a.showall').click(function(){
            var parent = $(this).parent();
            var ul = $('ul.replies', parent).first();
            $.get($(this).attr('href'), function(data){
                $(ul).html(data);
            });
            $(this).remove();
            return false;
        });

        if(opts.user_id){
            $('.comment-remove-'+opts.user_id).css({'display': 'inline'});
            $('.comment-remove').click(function(){
                var parent = $(this).parent().parent();
                $('form', parent).remove();
                var action = $('a', this).attr('href');
                var frm = $('.remove-form').last().clone();
                $('a.remove-cancel', frm).click(function(){ 
                    frm.remove(); 
                    return false;
                });
                frm.submit(function(){
                    $.post(action, $(this).serialize(), function(){
                        parent.remove();
                    });
                });
                frm.css({'display': 'block'});
                parent.append(frm);
                return false;
            });

            var frm = $('#tcc form').first();
            $(frm).submit(function(){
                $.post($(this).attr('action'), $(this).serialize(), function(data){
                    $('ul#tcc').append(data);
                    $('#id_comment', frm).val('');
                    var latest = $('ul#tcc li.comment').last();
                    $(document).tcc(opts);
                    if(!isScrolledIntoView(latest)){
                        $(document).scrollTop($(latest).offset().top-300);
                    }
                });
                return false;
            });
            
            $('.comment-reply').css({'display': 'inline'});
            $('.comment-reply').click(function(){
                var parent = $(this).parent().parent();
                $('form', parent).remove();
                var frm = $('#tcc form').first().clone();
                $('#id_parent', frm).val($('a', this).attr('id').slice(5));
                $(frm).submit(function(){
                    $.post($(this).attr('action'), $(this).serialize(), function(comment){
                        $(frm).remove();
                        if($('ul.replies', parent).length == 0){ $(parent).append('<ul class="replies"/>');}
                        $('ul.replies', parent).append(data);
                        $(document).tcc(opts);
                    });
                    return false;
                });
                parent.append(frm);
                if(!isScrolledIntoView(frm)){
                    $(document).scrollTop($(frm).offset().top-300);
                }
                return false;
            });
        }
    }

})(jQuery);
