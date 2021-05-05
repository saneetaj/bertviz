import json
import os
import uuid

from IPython.core.display import display, HTML, Javascript

from .util import format_special_chars, format_attention


def head_view(
        attention=None,
        tokens=None,
        sentence_b_start=None,
        prettify_tokens=True,
        layer=None,
        heads=None,
        encoder_attention=None,
        decoder_attention=None,
        cross_attention=None,
        encoder_tokens=None,
        decoder_tokens=None,
):
    """Render head view

        Args:
            For self-attention models:
                attention: list of ``torch.FloatTensor``(one for each layer) of shape
                    ``(batch_size(must be 1), num_heads, sequence_length, sequence_length)``
                tokens: list of tokens
                sentence_b_start: index of first wordpiece in sentence B if input text is sentence pair (optional)
            For encoder-decoder models:
                encoder_attention: list of ``torch.FloatTensor``(one for each layer) of shape
                    ``(batch_size(must be 1), num_heads, encoder_sequence_length, encoder_sequence_length)``
                decoder_attention: list of ``torch.FloatTensor``(one for each layer) of shape
                    ``(batch_size(must be 1), num_heads, decoder_sequence_length, decoder_sequence_length)``
                cross_attention: list of ``torch.FloatTensor``(one for each layer) of shape
                    ``(batch_size(must be 1), num_heads, decoder_sequence_length, encoder_sequence_length)``
                encoder_tokens: list of tokens for encoder input
                decoder_tokens: list of tokens for decoder input
            For all models:
                prettify_tokens: indicates whether to remove special characters in wordpieces, e.g. Ġ
                layer: index of layer to show in visualization when first loads. If non specified, defaults to layer 0.
                heads: indices of heads to show in visualization when first loads. If non specified, defaults to all.
    """

    attn_data = []
    if attention is not None:
        if tokens is None:
            raise ValueError("'tokens' is required")
        if encoder_attention is not None or decoder_attention is not None or cross_attention is not None \
                or encoder_tokens is not None or decoder_tokens is not None:
            raise ValueError("If you specify 'attention' you may not specify any encoder-decoder arguments. This"
                             " argument is only for self-attention models.")
        attention = format_attention(attention)
        if sentence_b_start is None:
            attn_data.append(
                {
                    'name': None,
                    'attn': attention.tolist(),
                    'left_text': tokens,
                    'right_text': tokens
                }
            )
        else:
            slice_a = slice(0, sentence_b_start)  # Positions corresponding to sentence A in input
            slice_b = slice(sentence_b_start, len(tokens))  # Position corresponding to sentence B in input
            attn_data.append(
                {
                    'name': 'All',
                    'attn': attention.tolist(),
                    'left_text': tokens,
                    'right_text': tokens
                }
            )
            attn_data.append(
                {
                    'name': 'Sentence A -> Sentence A',
                    'attn': attention[:, :, slice_a, slice_a].tolist(),
                    'left_text': tokens[slice_a],
                    'right_text': tokens[slice_a]
                }
            )
            attn_data.append(
                {
                    'name': 'Sentence B -> Sentence B',
                    'attn': attention[:, :, slice_b, slice_b].tolist(),
                    'left_text': tokens[slice_b],
                    'right_text': tokens[slice_b]
                }
            )
            attn_data.append(
                {
                    'name': 'Sentence A -> Sentence B',
                    'attn': attention[:, :, slice_a, slice_b].tolist(),
                    'left_text': tokens[slice_a],
                    'right_text': tokens[slice_b]
                }
            )
            attn_data.append(
                {
                    'name': 'Sentence B -> Sentence A',
                    'attn': attention[:, :, slice_b, slice_a].tolist(),
                    'left_text': tokens[slice_b],
                    'right_text': tokens[slice_a]
                }
            )
    elif encoder_attention is not None or decoder_attention is not None or cross_attention is not None:
        if encoder_attention is not None:
            if encoder_tokens is None:
                raise ValueError("'encoder_tokens' required if 'encoder_attention' is not None")
            encoder_attention = format_attention(encoder_attention)
            attn_data.append(
                {
                    'name': 'Encoder',
                    'attn': encoder_attention.tolist(),
                    'left_text': encoder_tokens,
                    'right_text': encoder_tokens
                }
            )
        if decoder_attention is not None:
            if decoder_tokens is None:
                raise ValueError("'decoder_tokens' required if 'decoder_attention' is not None")
            decoder_attention = format_attention(decoder_attention)
            attn_data.append(
                {
                    'name': 'Decoder',
                    'attn': decoder_attention.tolist(),
                    'left_text': decoder_tokens,
                    'right_text': decoder_tokens
                }
            )
        if cross_attention is not None:
            if encoder_tokens is None:
                raise ValueError("'encoder_tokens' required if 'cross_attention' is not None")
            if decoder_tokens is None:
                raise ValueError("'decoder_tokens' required if 'cross_attention' is not None")
            cross_attention = format_attention(cross_attention)
            attn_data.append(
                {
                    'name': 'Cross',
                    'attn': cross_attention.tolist(),
                    'left_text': decoder_tokens,
                    'right_text': encoder_tokens
                }
            )
    else:
        raise ValueError("You must specify at least one attention argument.")


    # Generate unique div id to enable multiple visualizations in one notebook
    vis_id = 'bertviz-%s'%(uuid.uuid4().hex)

    # Compose html
    if len(attn_data) > 1:
        options = '\n'.join(
            f'<option value="{i}">{attn_data[i]["name"]}</option>'
            for i, d in enumerate(attn_data)
        )
        select_html = f'Attention: <select id="filter">{options}</select>'
    else:
        select_html = ""
    vis_html = f"""      
        <div id='%s'>
            <span style="user-select:none">
                Layer: <select id="layer"></select>
                {select_html}
            </span>
            <div id='vis'></div>
        </div>
    """%(vis_id)

    for d in attn_data:
        attn_seq_len_left = len(d['attn'][0][0])
        if attn_seq_len_left != len(d['left_text']):
            raise ValueError(
                f"Attention has {attn_seq_len_left} positions, while number of tokens is {len(d['left_text'])} "
                f"for tokens: {' '.join(d['left_text'])}"
            )
        attn_seq_len_right = len(d['attn'][0][0][0])
        if attn_seq_len_right != len(d['right_text']):
            raise ValueError(
                f"Attention has {attn_seq_len_right} positions, while number of tokens is {len(d['right_text'])} "
                f"for tokens: {' '.join(d['right_text'])}"
            )
        if prettify_tokens:
            d['left_text'] = format_special_chars(d['left_text'])
            d['right_text'] = format_special_chars(d['right_text'])

    params = {
        'attention': attn_data,
        'default_filter': "0",
        'root_div_id': vis_id,
        'layer': layer,
        'heads': heads
    }

    # require.js must be imported for Colab or JupyterLab:
    display(HTML('<script src="https://cdnjs.cloudflare.com/ajax/libs/require.js/2.3.6/require.min.js"></script>'))
    display(HTML(vis_html))
    __location__ = os.path.realpath(
        os.path.join(os.getcwd(), os.path.dirname(__file__)))
    vis_js = open(os.path.join(__location__, 'head_view.js')).read().replace("PYTHON_PARAMS", json.dumps(params))
    display(Javascript(vis_js))